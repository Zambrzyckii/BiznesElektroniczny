"""Adresy wszystkich produktów i kategorii z sitemap sklepu.

Uruchomienie w folderze scraper/:  python sitemap.py  ->  ../scraper-results/sitemap.json

Sitemapy są brane z linii "Sitemap:" w robots.txt; gdy ich tam nie ma albo nic
nie zwracają, z config.SITEMAP_FALLBACK. Indeksy sitemap są rozwijane.
"""

import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import config
from fetcher import Fetcher

HERE = Path(__file__).parent
OUTPUT = HERE.parent / "scraper-results" / "sitemap.json"

log = logging.getLogger("scraper")

# Ścieżki z dwoma segmentami, które nie są produktami (strony CMS, blog)
NIE_PRODUKTY = ("strona", "blog", "content", "module")


def parse_sitemap(dane):
    """Bajty sitemapy -> (czy to indeks sitemap, lista adresów z <loc>)."""
    root = ET.fromstring(dane)
    czy_indeks = root.tag.endswith("sitemapindex")
    # tylko <loc> bezpośrednio w <url>/<sitemap>; <image:loc> (zdjęcia) leży głębiej
    adresy = [el.text.strip() for wpis in root for el in wpis
              if el.tag.split("}")[-1] == "loc" and el.text]
    return czy_indeks, adresy


def url_kind(url):
    """Rodzaj strony z kształtu adresu: "product", "category" albo None.

    produkt:   /batony-klasyczne/30-baton-chrupiacy-orzech-35-g
    kategoria: /32-batony-klasyczne
    """
    segmenty = [s for s in urlsplit(url).path.split("/") if s]
    if len(segmenty) == 1 and re.match(r"\d+-", segmenty[0]):
        return "category"
    if len(segmenty) == 2 and re.match(r"\d+-", segmenty[1]) and segmenty[0] not in NIE_PRODUKTY:
        return "product"
    return None


def same_host(url, base_url):
    """Adres sitemapy na hoście sklepu (robots.txt może wskazywać starą domenę)."""
    baza = urlsplit(base_url)
    czesci = urlsplit(url)
    return urlunsplit((baza.scheme, baza.netloc, czesci.path, czesci.query, ""))


def collect_sitemap_urls(fetcher, start_urls, base_url):
    """{"products": [...], "categories": [...]} ze wszystkich podanych sitemap (z rozwinięciem indeksów)."""
    wynik = {"products": [], "categories": []}
    kolejka = [same_host(u, base_url) for u in start_urls]
    odwiedzone = set()
    while kolejka:
        url = kolejka.pop(0)
        if url in odwiedzone:
            continue
        odwiedzone.add(url)
        try:
            czy_indeks, adresy = parse_sitemap(fetcher.get_bytes(url))
        except Exception as e:  # brak sitemapy lub niepoprawny XML: próbujemy pozostałych
            log.warning("Sitemapa %s pominięta: %r", url, e)
            continue
        if czy_indeks:
            kolejka += [same_host(a, base_url) for a in adresy]
            continue
        log.info("Sitemapa %s: %d adresów", url, len(adresy))
        for adres in adresy:
            rodzaj = url_kind(adres)
            if rodzaj:
                wynik[{"product": "products", "category": "categories"}[rodzaj]].append(adres)
    return {klucz: list(dict.fromkeys(lista)) for klucz, lista in wynik.items()}


def load_sitemap_urls(fetcher, base_url=config.BASE_URL):
    """Sitemapy z robots.txt, a gdy nic nie dadzą: z config.SITEMAP_FALLBACK."""
    wynik = collect_sitemap_urls(fetcher, fetcher.sitemaps, base_url)
    if not wynik["products"]:
        log.info("robots.txt nie dał sitemapy produktów, używam config.SITEMAP_FALLBACK")
        wynik = collect_sitemap_urls(fetcher, config.SITEMAP_FALLBACK, base_url)
    log.info("Z sitemap: %d produktów, %d kategorii", len(wynik["products"]), len(wynik["categories"]))
    return wynik


def main():
    (HERE / "logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                        handlers=[logging.FileHandler(HERE / "logs" / "scraper.log", encoding="utf-8"),
                                  logging.StreamHandler()])
    fetcher = Fetcher.for_site(config.BASE_URL, HERE / "cache")
    wynik = load_sitemap_urls(fetcher)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(wynik, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("KONIEC: %s, %d zapytań do sieci, %d z cache", OUTPUT.name, fetcher.network_requests, fetcher.cache_hits)


if __name__ == "__main__":
    main()
