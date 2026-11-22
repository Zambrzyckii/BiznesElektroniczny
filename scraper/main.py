"""Scraper: kategorie -> produkty -> walidacja -> scraper-results/*.json.

Uruchomienie w folderze scraper/:  python main.py
Log z czasem każdego zapytania: logs/scraper.log
"""

import json
import logging
from pathlib import Path

import config
from fetcher import BlockedByRobots, Fetcher
from parsers import parse_category, parse_product, product_id_from_url
from sitemap import load_sitemap_urls
from validation import log_summary, validate_product

HERE = Path(__file__).parent
RESULTS_DIR = HERE.parent / "scraper-results"
CACHE_DIR = HERE / "cache"
LOG_FILE = HERE / "logs" / "scraper.log"

log = logging.getLogger("scraper")


def collect_product_urls(fetcher, tree):
    """{id_produktu: (adres, [kategoria, podkategoria], [dodatkowe kategorie])}.

    Produkt występujący w kilku podkategoriach ma kategorię domyślną w najmniejszej z nich,
    np. do "O smaku deserów" (3 produkty), a nie do "Mini batoniki - 6 sztuk" (30).
    Przypisanie do pierwszej znalezionej zostawiało podkategorie puste (docs/adr/0009-categories-vat-attributes.md).
    """
    gdzie = {}      # id -> [(kategoria, podkategoria), ...]
    adresy = {}     # id -> adres produktu
    rozmiar = {}    # (kategoria, podkategoria) -> liczba produktów

    # 1. członkostwo produktów we wszystkich podkategoriach
    for kategoria, podkategorie in tree.items():
        for podkategoria, adres in podkategorie.items():
            ids = set()
            strona = 1
            while adres:
                log.info("Kategoria %s > %s, strona %d", kategoria, podkategoria, strona)
                wynik = parse_category(fetcher.get(adres))
                for url in wynik["product_urls"]:
                    pid = product_id_from_url(url)
                    if pid is None or pid in ids:
                        continue
                    ids.add(pid)
                    adresy.setdefault(pid, url)
                    gdzie.setdefault(pid, []).append((kategoria, podkategoria))
                adres = wynik["next_page"]
                strona += 1
            rozmiar[(kategoria, podkategoria)] = len(ids)

    # 2. kategoria domyślna = najmniejsza podkategoria (przy remisie pierwsza wg config.py);
    #    pozostałe to dodatkowe powiązania, bez zbiorczych "Pozostałe ..."
    znalezione = {}
    for pid, miejsca in gdzie.items():
        najmniejsza = min(miejsca, key=lambda m: rozmiar[m])
        dodatkowe = [list(m) for m in miejsca if m != najmniejsza and not m[1].startswith("Pozostałe")]
        znalezione[pid] = (adresy[pid], list(najmniejsza), dodatkowe)

    log.info("Znaleziono %d unikalnych produktów", len(znalezione))
    return znalezione


def scrape_products(fetcher, znalezione):
    """(poprawne produkty, liczba odrzuconych)."""
    produkty, bledy = [], 0
    for i, (pid, (url, sciezka, dodatkowe)) in enumerate(znalezione.items(), start=1):
        try:
            dane = parse_product(fetcher.get(url))
        except (BlockedByRobots, RuntimeError, ValueError, KeyError) as e:
            bledy += 1
            log.error("Produkt %s (%s) pominięty: %r", pid, url, e)
            continue
        dane["category_path"] = sciezka  # z naszego drzewa; okruszki bywają "Wszystkie produkty"
        dane["extra_categories"] = dodatkowe
        produkt = validate_product(dane, url)
        if produkt is None:
            bledy += 1
            continue
        produkty.append(produkt)
        if i % 20 == 0:
            log.info("Postęp: %d / %d", i, len(znalezione))
    return produkty, bledy


def find_missing(fetcher, all_products_url, znalezione, z_sitemapy=(), pominiete=()):
    """Adresy produktów z listy "Wszystkie produkty" i z sitemapy, których nie ma w żadnej naszej podkategorii.

    pominiete: ID produktów świadomie pominiętych (config.EXCLUDED_PRODUCTS), np. torby, które nie są jedzeniem.
    """
    wszystkie = {}
    for url in z_sitemapy:
        pid = product_id_from_url(url)
        if pid is not None:
            wszystkie.setdefault(pid, url)
    adres = all_products_url
    while adres:
        wynik = parse_category(fetcher.get(adres))
        for url in wynik["product_urls"]:
            pid = product_id_from_url(url)
            if pid is not None:
                wszystkie.setdefault(pid, url)
        adres = wynik["next_page"]

    for pid in pominiete:
        if pid in wszystkie and pid not in znalezione:
            log.info("Produkt pominięty celowo (poza asortymentem, config.EXCLUDED_PRODUCTS): %s", wszystkie[pid])
    brakujace = [url for pid, url in wszystkie.items() if pid not in znalezione and pid not in pominiete]
    log.info("W sklepie (lista + sitemapa) jest %d produktów, w naszych kategoriach %d",
             len(wszystkie), len(znalezione))
    for url in brakujace:
        log.warning("Produkt poza naszymi kategoriami (dopisz kategorię w config.py): %s", url)
    return brakujace


def apply_manual_categories(znalezione, brakujace, reczne):
    """Dodaj zgubione produkty, którym ręcznie przypisano kategorię w config.MANUAL_CATEGORIES.

    Zwraca listę adresów, które nadal nie mają kategorii.
    """
    zostaly = []
    for url in brakujace:
        pid = product_id_from_url(url)
        if pid in reczne:
            znalezione[pid] = (url, list(reczne[pid]), [])
            log.info("Produkt %s dodany ręcznie do %s", url, " > ".join(reczne[pid]))
        else:
            zostaly.append(url)
    return zostaly


def build_categories(produkty, tree=None):
    """Lista kategorii i podkategorii z liczbą produktów (tylko niepuste).

    Kolejność jak w drzewie z config.py (tak samo jak w menu sklepu), a nie wg pierwszego produktu.
    """
    licznik = {}
    for p in produkty:
        kategoria, podkategoria = p["category_path"]
        licznik.setdefault(kategoria, {}).setdefault(podkategoria, 0)
        licznik[kategoria][podkategoria] += 1

    def kolejnosc(nazwy, wzor):
        wzor = list(wzor or [])
        return sorted(nazwy, key=lambda n: wzor.index(n) if n in wzor else len(wzor))

    tree = tree or {}
    return [
        {"name": kat, "subcategories": [{"name": pod, "products": licznik[kat][pod]}
                                        for pod in kolejnosc(licznik[kat], tree.get(kat))]}
        for kat in kolejnosc(licznik, tree)
    ]


def drop_unknown_extra_categories(produkty, kategorie):
    """Usuń z extra_categories podkategorie, których nie ma w categories.json.

    Np. zbiorcze "Mini batoniki - 6 sztuk" nie są niczyją kategorią domyślną, więc nie ma ich
    w categories.json; import nie miałby do czego przypiąć takiego powiązania.
    """
    istniejace = {(k["name"], s["name"]) for k in kategorie for s in k["subcategories"]}
    for p in produkty:
        p["extra_categories"] = [e for e in p["extra_categories"] if tuple(e) in istniejace]


def save_json(dane, plik):
    plik.parent.mkdir(parents=True, exist_ok=True)
    plik.write_text(json.dumps(dane, ensure_ascii=False, indent=2), encoding="utf-8")


def setup_logging():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
    )


def main():
    setup_logging()
    fetcher = Fetcher.for_site(config.BASE_URL, CACHE_DIR)

    sitemapa = load_sitemap_urls(fetcher)
    save_json(sitemapa, RESULTS_DIR / "sitemap.json")
    znalezione = collect_product_urls(fetcher, config.CATEGORY_TREE)
    brakujace = find_missing(fetcher, config.ALL_PRODUCTS_URL, znalezione, sitemapa["products"],
                             config.EXCLUDED_PRODUCTS)
    brakujace = apply_manual_categories(znalezione, brakujace, config.MANUAL_CATEGORIES)
    produkty, bledy = scrape_products(fetcher, znalezione)
    kategorie = build_categories(produkty, config.CATEGORY_TREE)
    drop_unknown_extra_categories(produkty, kategorie)

    save_json(produkty, RESULTS_DIR / "products.json")
    save_json(kategorie, RESULTS_DIR / "categories.json")

    log_summary(len(produkty), bledy, fetcher, poza_kategoriami=len(brakujace))


if __name__ == "__main__":
    main()
