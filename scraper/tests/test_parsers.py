"""Testy parserów na zapisanych stronach z tests/fixtures/; oczekiwane wartości pochodzą z tych stron."""

from pathlib import Path

import pytest

from parsers import nearest_vat, parse_category, parse_product, product_id_from_url

FIXTURES = Path(__file__).parent / "fixtures"


def wczytaj(nazwa):
    return (FIXTURES / nazwa).read_text(encoding="utf-8")


# --- produkty --------------------------------------------------------------

def test_produkt_z_jednym_zdjeciem():
    p = parse_product(wczytaj("product_simple.html"))
    assert p["id"] == 237
    assert p["name"] == "Baton PROTEIN karmel z niskim IG 45g"
    assert p["price_gross"] == 4.39
    assert p["vat_rate"] == 5                 # 4.39 / 4.180952 = 1.05
    assert p["weight_kg"] == 0.045
    assert p["available"] is True
    assert p["category_path"] == ["Naturalne słodycze", "Batony proteinowe"]
    assert p["old_price_gross"] == 5.49           # ten baton też jest w promocji (meta standard_amount)
    assert p["description"].startswith("Pyszny baton proteinowy o smaku karmelu")
    assert len(p["images"]) == 1
    assert p["images"][0].endswith("755-large_default/mini-batoniki.jpg")


def test_produkt_z_wieloma_zdjeciami():
    p = parse_product(wczytaj("product_many_images.html"))
    assert p["name"] == "Baton nerkowce & kokos - 35g"   # "&" poprawnie odkodowany
    assert p["price_gross"] == 2.59
    assert p["old_price_gross"] is None                  # nie jest w promocji
    assert p["description"].startswith("Ten baton to kwintesencja naturalności")
    # cała galeria, nie tylko og:image
    assert len(p["images"]) == 2
    assert all("large_default" in u for u in p["images"])


def test_produkt_w_promocji():
    p = parse_product(wczytaj("product_promo.html"))
    assert p["price_gross"] == 7.99
    assert p["old_price_gross"] == 8.99
    assert p["lowest_price_30d"] == 8.99


def test_produkt_niedostepny():
    p = parse_product(wczytaj("product_unavailable.html"))
    assert p["available"] is False
    assert p["price_gross"] == 44.85                     # w źródle 44.8455, zaokrąglamy do groszy
    assert p["category_path"] == ["Zestawy", "Zestawy słodyczy"]


def test_sklad_jako_atrybut():
    p = parse_product(wczytaj("product_many_images.html"))
    assert p["attributes"]["Składniki"].startswith("daktyle suszone")
    assert p["attributes"]["Składniki"].endswith("mąka ryżowa).")   # kończy się przed alergenami
    assert p["attributes"]["Wartość energetyczna (100 g)"] == "1594 kJ / 380 kcal"


def test_sklad_bez_pogrubienia():
    # tu etykieta "Składniki:" nie jest pogrubiona
    p = parse_product(wczytaj("product_promo.html"))
    assert p["attributes"]["Składniki"].startswith("daktyle suszone (95 %)")


def test_zestaw_ma_liste_produktow_jako_atrybut():
    p = parse_product(wczytaj("product_unavailable.html"))
    assert p["attributes"]["Zawartość zestawu"] == "15 x Baton proteinowy - krem orzechowy & sól - 45g"
    assert "Składniki" not in p["attributes"]   # zestaw nie ma własnego składu


def test_pudelko_prezentowe_z_linkami_do_smakow():
    p = parse_product(wczytaj("product_gift_links.html"))   # Tuba prezentowa
    zawartosc = p["attributes"]["Zawartość zestawu"].split("; ")
    assert len(zawartosc) == 5
    assert zawartosc[0] == "Mini batoniki o smaku a la ciasto porzeczkowe"
    assert "Skład i wartości odżywcze" not in p["attributes"]["Zawartość zestawu"]  # link-zakładka pominięty


def test_pudelko_prezentowe_z_opisem_tekstowym():
    p = parse_product(wczytaj("product_gift_box.html"))     # Zestaw Prezentowy - nowe smaki
    zawartosc = p["attributes"]["Zawartość zestawu"]
    assert zawartosc.startswith("Mini batoniki à la ciasto porzeczkowe - 108 g (6 szt.)")
    assert p["weight_kg"] is None                        # źródło nie podaje wagi zestawu
    assert len(p["images"]) == 4
    assert zawartosc.endswith("Mini batoniki mango lassi - 102 g (6 szt.)")


def test_kazdy_produkt_ma_jakis_atrybut():
    for plik in ["product_simple.html", "product_many_images.html", "product_promo.html", "product_unavailable.html",
                 "product_gift_links.html", "product_gift_box.html"]:
        assert parse_product(wczytaj(plik))["attributes"], plik


@pytest.mark.parametrize("plik, gramatura", [
    ("product_simple.html", "45 g"),           # "Baton PROTEIN karmel z niskim IG 45g"
    ("product_many_images.html", "35 g"),      # "Baton nerkowce & kokos - 35g"
    ("product_unavailable.html", "15 x 45 g"),  # "... & sól 15 x 45g"
])
def test_gramatura_z_nazwy(plik, gramatura):
    assert parse_product(wczytaj(plik))["attributes"]["Gramatura"] == gramatura


def test_brak_gramatury_w_nazwie():
    assert "Gramatura" not in parse_product(wczytaj("product_promo.html"))["attributes"]  # "Datesy ... yuzu"


def test_cechy_spod_opisu():
    p = parse_product(wczytaj("product_many_images.html"))
    assert p["attributes"]["Cechy"] == "krótki skład; 0% dodatku cukru; tylko 133 kcal; 97% owoców i orzechów"


def test_najnizsza_cena_z_30_dni():
    assert parse_product(wczytaj("product_simple.html"))["lowest_price_30d"] == 4.99       # "4,99 pln"
    assert parse_product(wczytaj("product_unavailable.html"))["lowest_price_30d"] == 59.85
    assert parse_product(wczytaj("product_many_images.html"))["lowest_price_30d"] is None   # bez promocji


def test_brak_encji_amp_w_nazwie_i_opisie():
    p = parse_product(wczytaj("product_many_images.html"))
    assert "&amp;" not in p["name"] and "&amp;" not in p["description"]


def test_polskie_znaki():
    p = parse_product(wczytaj("product_unavailable.html"))
    assert "ó" in p["name"]                              # "sól"
    assert parse_product(wczytaj("product_gift_box.html"))["description"].startswith("Piękny prezent pełen dobra")


# --- przypadki brzegowe na małych, sztucznych stronach ---------------------------------------

def strona(produkt, meta=""):
    """Minimalna karta produktu: blok JSON-LD Product i ewentualne meta tagi."""
    import json
    return (f'<html><head>{meta}<script type="application/ld+json">{json.dumps(produkt)}</script>'
            "</head><body></body></html>")


OFERTA = {"price": "2.675", "url": "https://dobrakaloria.pl/batony/7-baton", "availability": "InStock",
          "image": ["https://dobrakaloria.pl/1-large_default/a.jpg"]}


def test_podwojnie_zakodowany_ampersand_w_json_ld():
    # w źródle część nazw ma "&amp;" w JSON-LD; po json.loads zostaje "&amp;", a parser ma dać "&"
    p = parse_product(strona({"@type": "Product", "name": "Baton jabłko &amp; cynamon 35g",
                              "description": "Słodki &amp; chrupiący", "offers": OFERTA}))
    assert p["name"] == "Baton jabłko & cynamon 35g"
    assert p["description"] == "Słodki & chrupiący"


def test_cena_zaokraglana_do_groszy_w_gore_od_polowy():
    assert parse_product(strona({"@type": "Product", "name": "X", "offers": OFERTA}))["price_gross"] == 2.68


def test_waga_jako_liczba():
    p = parse_product(strona({"@type": "Product", "name": "X", "weight": 0.05, "offers": OFERTA}))
    assert p["weight_kg"] == 0.05


@pytest.mark.parametrize("produkt, meta", [
    ({"@type": "Product", "name": "X"}, ""),                                     # brak oferty
    ({"@type": "Product", "name": "X", "offers": {"url": "u"}}, ""),             # oferta bez ceny
    ({"@type": "Product", "name": "X", "offers": OFERTA},
     '<meta property="product:pretax_price:amount" content="0">'),               # netto 0
    ({"@type": "Product", "name": "X", "offers": {**OFERTA, "price": "NaN"}}, ""),  # cena NaN
    ({"@type": "Product", "name": "X", "offers": {**OFERTA, "price": "-1"}}, ""),   # cena ujemna
    ({"@type": "Product", "offers": OFERTA}, ""),                                # brak nazwy
    ({"@type": "Product", "name": "X", "description": None, "offers": OFERTA}, ""),  # opis null
    ({"@type": "Product", "name": "X", "offers": OFERTA},
     '<meta property="product:price:standard_amount" content="abc">'),            # zła cena przed obniżką
])
def test_nietypowa_strona_daje_czytelny_blad(produkt, meta):
    with pytest.raises(ValueError):
        parse_product(strona(produkt, meta))


# --- kategoria -------------------------------------------------------------

def test_lista_produktow_w_kategorii():
    k = parse_category(wczytaj("category.html"))
    assert len(k["product_urls"]) == 11      # tylko główna lista, bez produktów z menu
    assert k["product_urls"][0].endswith("/301-kulki-sniadaniowe-gorzka-belgijska-czekolada-40-g")
    assert k["next_page"] is None            # ta kategoria mieści się na jednej stronie


def test_kategoria_z_kolejnymi_stronami():
    k = parse_category(wczytaj("category_paged.html"))   # "Wszystkie produkty", strona 1 z 12
    assert len(k["product_urls"]) == 12
    assert k["next_page"] == "https://dobrakaloria.pl/2-wszystkie-produkty?page=2"


# --- VAT -------------------------------------------------------------------

@pytest.mark.parametrize("wyliczony, stawka", [
    (5.0, 5),
    (8.0001, 8),
    (23.0, 23),
    (9.37, 8),    # zestaw z produktami o różnych stawkach
    (10.9, 8),
    (16.0, 23),
])
def test_vat_do_prawdziwej_stawki(wyliczony, stawka):
    assert nearest_vat(wyliczony) == stawka


# --- ID z adresu -----------------------------------------------------------

def test_id_z_adresu():
    assert product_id_from_url("https://dobrakaloria.pl/batony-klasyczne/36-baton-nerkowce-kokos-35-g") == 36
    # ten sam produkt w innej ścieżce -> to samo ID
    assert product_id_from_url("https://dobrakaloria.pl/wszystkie-produkty/36-baton-nerkowce-kokos-35-g") == 36
