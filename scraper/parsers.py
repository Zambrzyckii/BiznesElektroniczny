"""Parsery stron sklepu: HTML -> słowniki z danymi.

Moduł nie wykonuje zapytań sieciowych, więc jest testowany na zapisanych
stronach z tests/fixtures/.
"""

import html as html_lib
import json
import logging
import re
from decimal import ROUND_HALF_UP, Decimal

from bs4 import BeautifulSoup

log = logging.getLogger("scraper")

# ---------------------------------------------------------------------------
# Pomocnicy
# ---------------------------------------------------------------------------

def _json_ld(soup, typ):
    """Zwróć pierwszy blok JSON-LD (<script type="application/ld+json">) danego typu, np. "Product".

    JSON-LD zawiera dane strukturalne produktu, więc jest stabilniejszym źródłem
    niż elementy HTML zależne od motywu sklepu.
    """
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            dane = json.loads(script.string or script.get_text())
        except json.JSONDecodeError:
            continue
        if isinstance(dane, dict) and dane.get("@type") == typ:
            return dane
    return None


def _meta(soup, nazwa):
    """Zwróć wartość content="..." z <meta property="nazwa">, albo None."""
    tag = soup.find("meta", property=nazwa)
    return tag["content"] if tag else None


def _do_groszy(wartosc):
    """Zaokrąglij cenę do groszy jak w handlu (44.8455 -> 44.85, 2.675 -> 2.68).

    Decimal zamiast round(), bo round() na liczbach zmiennoprzecinkowych daje round(2.675, 2) == 2.67.
    """
    return float(Decimal(str(wartosc)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


POLISH_VAT_RATES = (0, 5, 8, 23)  # %


def nearest_vat(wyliczony):
    """Dopasuj wyliczoną stawkę VAT do najbliższej obowiązującej.

    Zestawy łączą produkty o różnych stawkach, przez co stawka wyliczona z cen
    wychodzi np. 9.4%. PrestaShop wymaga jednej stawki na produkt (docs/source-analysis.md, sekcja VAT).
    """
    stawka = min(POLISH_VAT_RATES, key=lambda s: abs(s - wyliczony))
    if abs(stawka - wyliczony) > 0.5:
        log.warning("VAT wyliczony %.2f%% nie jest prawdziwą stawką, przyjmuję %d%%", wyliczony, stawka)
    return stawka


def product_id_from_url(url):
    """ID produktu z adresu: .../batony-klasyczne/36-baton-nerkowce-kokos-35-g -> 36.

    Ten sam produkt występuje pod różnymi ścieżkami kategorii, więc duplikaty
    rozpoznajemy po ID, a nie po adresie.
    """
    ostatni_kawalek = url.rstrip("/").split("/")[-1]
    dopasowanie = re.match(r"(\d+)-", ostatni_kawalek)
    return int(dopasowanie.group(1)) if dopasowanie else None


# ---------------------------------------------------------------------------
# Karta produktu
# ---------------------------------------------------------------------------

def parse_product(html):
    """Karta produktu (HTML) -> słownik z danymi produktu."""
    try:
        return _parse_product(html)
    except ValueError:
        raise
    except (KeyError, TypeError, AttributeError, ArithmeticError) as blad:
        # nietypowa strona: jeden rodzaj błędu z opisem, żeby main.py zapisał go w logu i szedł dalej
        raise ValueError(f"Nietypowa karta produktu ({type(blad).__name__}: {blad})") from blad


def _parse_product(html):
    soup = BeautifulSoup(html, "html.parser")

    produkt = _json_ld(soup, "Product")
    if produkt is None:
        raise ValueError("Brak bloku JSON-LD typu Product")
    # Nietypowa strona ma dawać czytelny ValueError (trafia do logu z adresem), a nie KeyError/TypeError
    oferta = produkt.get("offers")
    if isinstance(oferta, list) and oferta:
        oferta = oferta[0]
    if not isinstance(oferta, dict) or "price" not in oferta:
        raise ValueError("JSON-LD Product nie ma oferty z ceną (offers.price)")

    # Cena brutto z JSON-LD, netto z meta tagu: VAT = brutto / netto - 1
    try:
        brutto = float(oferta["price"])
        netto_txt = _meta(soup, "product:pretax_price:amount")
        netto = float(netto_txt) if netto_txt else None
    except (TypeError, ValueError) as blad:
        raise ValueError(f"Niepoprawna cena w JSON-LD lub meta: {blad}") from blad
    if not brutto > 0:  # odrzuca też NaN
        raise ValueError(f"Niepoprawna cena brutto: {oferta['price']}")
    if netto is not None and netto <= 0:
        raise ValueError(f"Niepoprawna cena netto: {netto_txt}")
    vat = nearest_vat((brutto / netto - 1) * 100) if netto else None

    # cena przed obniżką, tylko przy promocjach
    stara_txt = _meta(soup, "product:price:standard_amount")
    stara_cena = _do_groszy(stara_txt) if stara_txt else None

    # waga to zwykle {"value": "0.045", "unitCode": "kg"}, ale bywa samą liczbą
    waga = produkt.get("weight")
    if isinstance(waga, dict):
        waga = waga.get("value")

    # offers.image to pełna galeria w rozmiarze large_default; pojedyncze zdjęcie bywa stringiem.
    # Zapasowo meta og:image (też cała galeria), na końcu Product.image (tylko pierwsze zdjęcie).
    zdjecia = (oferta.get("image")
               or [t["content"] for t in soup.find_all("meta", property="og:image") if t.get("content")]
               or produkt.get("image") or [])
    if isinstance(zdjecia, str):
        zdjecia = [zdjecia]
    zdjecia = list(dict.fromkeys(zdjecia))  # bez duplikatów, z zachowaniem kolejności

    # Ścieżka z okruszków; main.py (w #23) nadpisuje ją kategorią z naszego drzewa
    okruszki = _json_ld(soup, "BreadcrumbList")
    sciezka = []
    if okruszki:
        nazwy = [el["item"]["name"] for el in okruszki["itemListElement"]]
        sciezka = nazwy[1:-1]  # bez "Strona główna" i nazwy produktu

    # Sklep nie ma cech typu kolor/rozmiar; atrybuty pochodzą z opisu produktu (docs/source-analysis.md)
    atrybuty = {}
    nazwa = html_lib.unescape(produkt["name"]).strip()
    gramatura = _find_grammage(nazwa)
    if gramatura:
        atrybuty["Gramatura"] = gramatura
    sklad = _find_ingredients(soup)
    if sklad:
        atrybuty["Składniki"] = sklad
    energia = _find_energy(soup)
    if energia:
        atrybuty["Wartość energetyczna (100 g)"] = energia
    zawartosc = _find_pack_contents(soup, ma_sklad=bool(sklad))
    if zawartosc:
        atrybuty["Zawartość zestawu"] = zawartosc
    # wyróżniki pod opisem, np. "0% dodatku cukru"; "fetaures" to pisownia z motywu sklepu
    cechy = [li.get_text(" ", strip=True) for li in soup.select("ul.fetaures-top li")]
    if cechy:
        atrybuty["Cechy"] = "; ".join(cechy)

    url = oferta.get("url") or _meta(soup, "og:url")

    return {
        "id": product_id_from_url(url),
        "source_url": url,
        # część tekstów w JSON-LD ma podwójnie zakodowane encje (&amp;)
        "name": nazwa,
        "description": html_lib.unescape(produkt.get("description", "")).strip(),
        "price_gross": _do_groszy(oferta["price"]),
        "old_price_gross": stara_cena,
        "lowest_price_30d": _find_lowest_price_30d(soup),
        "vat_rate": vat,
        "weight_kg": float(waga) if waga else None,
        "available": "InStock" in oferta.get("availability", ""),
        "category_path": sciezka,
        "attributes": atrybuty,
        "images": zdjecia,
    }


def _find_lowest_price_30d(soup):
    """Najniższa cena z 30 dni (Omnibus), np. "4,99 pln" -> 4.99; None poza promocjami."""
    napis = soup.find(string=re.compile("Najniższa cena z 30 dni"))
    if napis is None:
        return None
    akapit = napis.find_parent("p") or napis.parent
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*pln", akapit.get_text(" ", strip=True), re.IGNORECASE)
    return float(m.group(1).replace(",", ".")) if m else None


def _find_grammage(nazwa):
    """Gramatura z nazwy produktu: "Baton ... - 35g" -> "35 g", "... 15 x 45g" -> "15 x 45 g"."""
    trafienia = re.findall(r"(?:(\d+)\s*x\s*)?(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l)\b", nazwa, re.IGNORECASE)
    if not trafienia:
        return None
    sztuki, ilosc, jednostka = trafienia[-1]
    return (f"{sztuki} x " if sztuki else "") + f"{ilosc} {jednostka.lower()}"


def _tab_text(soup):
    """Tekst zakładki "Skład i wartości odżywcze" w jednej linii, z ujednoliconymi spacjami."""
    zakladka = soup.select_one("#tabdesc")
    if zakladka is None:
        return ""
    tekst = zakladka.get_text(" ", strip=True)
    tekst = re.sub(r"\s+", " ", tekst)
    return re.sub(r"\s+([,.)])", r"\1", tekst)      # "orzechy , sezam" -> "orzechy, sezam"


def _find_ingredients(soup):
    """Tekst po "Składniki:" do informacji o alergenach.

    Szukamy w tekście, a nie po <strong>, bo etykieta nie zawsze jest pogrubiona.
    """
    m = re.search(r"Składniki:\s*(.+?)(?=\s*(?:Produkt może|Może zawierać|Uwaga|Bez dodatku|$))", _tab_text(soup))
    return m.group(1).strip() if m else None


def _find_energy(soup):
    """Wartość energetyczna na 100 g (pierwsza kolumna tabeli), np. "1264 kJ / 299 kcal"."""
    m = re.search(r"Wartość energetyczna\s*([\d\s,.]+kJ\s*/\s*[\d,.]+\s*kcal)", _tab_text(soup))
    if not m:
        return None
    wynik = re.sub(r"\s*/\s*", " / ", m.group(1)).strip()
    return re.sub(r"(\d)\s*kJ", r"\1 kJ", wynik)  # "1594kJ" -> "1594 kJ"


def _find_pack_contents(soup, ma_sklad=False):
    """Lista produktów w zestawie, np. "3 x Baton jabłko & cynamon - 35g; 4 x Baton ...".

    Sklep podaje zawartość na trzy sposoby, sprawdzane po kolei:
      1. sekcja "Zestaw zawiera:" modułu pakietów (#ap5-product-list)
      2. linki do produktów w zakładce składu (pudełka prezentowe)
      3. zdanie "W skład zestawu wchodzi ...: <lista>"
    """
    tytuly = [t.get_text(" ", strip=True) for t in soup.select("#ap5-product-list .ap5-pack-product-title")]
    if tytuly:
        return "; ".join(tytuly)

    # 2 i 3 tylko dla produktów bez składu: link w opisie pojedynczego produktu nie oznacza zestawu
    if ma_sklad:
        return None

    zakladka = soup.select_one("#tabdesc")
    if zakladka is not None:
        linki = [a.get_text(" ", strip=True) for a in zakladka.select("a[href]")
                 if product_id_from_url(a["href"]) is not None]
        if linki:
            return "; ".join(dict.fromkeys(linki))

    m = re.search(r"W skład zestawu wchodzi[^:]*:\s*(.+)$", _tab_text(soup))
    return m.group(1).strip() if m else None


# ---------------------------------------------------------------------------
# Lista produktów w kategorii
# ---------------------------------------------------------------------------

def parse_category(html):
    """Strona kategorii -> adresy produktów i adres następnej strony (None na ostatniej)."""
    soup = BeautifulSoup(html, "html.parser")

    # Tylko główna lista; menu na górze strony też zawiera kafelki produktów
    adresy = []
    for kafelek in soup.select("#js-product-list .product-miniature"):
        link = kafelek.select_one("a[href]")
        if link:
            adresy.append(link["href"])
    adresy = list(dict.fromkeys(adresy))

    nastepna = soup.select_one('#js-product-list a[rel="next"]')
    return {
        "product_urls": adresy,
        "next_page": nastepna["href"] if nastepna else None,
    }
