"""Testy sitemap bez sieci: FakeFetcher serwuje pliki XML z fixtures/."""

from pathlib import Path

from sitemap import collect_sitemap_urls, load_sitemap_urls, parse_sitemap, same_host, url_kind

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://dobrakaloria.pl"


class FakeFetcher:
    def __init__(self, strony, sitemaps=()):
        self.strony = strony
        self.sitemaps = list(sitemaps)
        self.pobrane = []

    def get_bytes(self, url):
        self.pobrane.append(url)
        if url not in self.strony:
            raise RuntimeError(f"404 {url}")
        return (FIXTURES / self.strony[url]).read_bytes()


STRONY = {
    f"{BASE}/sitemap.xml": "sitemap_index.xml",
    f"{BASE}/sitemap-products.xml": "sitemap_products.xml",
    f"{BASE}/sitemap-categories.xml": "sitemap_categories.xml",
}


def test_parse_urlset():
    czy_indeks, adresy = parse_sitemap((FIXTURES / "sitemap_products.xml").read_bytes())
    assert czy_indeks is False
    assert adresy[0] == f"{BASE}/batony-klasyczne/30-baton-chrupiacy-orzech-35-g"
    assert not any(a.endswith(".jpg") for a in adresy)   # bez <image:loc>
    assert len(adresy) == 4


def test_parse_indeks():
    czy_indeks, adresy = parse_sitemap((FIXTURES / "sitemap_index.xml").read_bytes())
    assert czy_indeks is True
    assert len(adresy) == 2


def test_rodzaj_adresu():
    assert url_kind(f"{BASE}/batony-klasyczne/30-baton-chrupiacy-orzech-35-g") == "product"
    assert url_kind(f"{BASE}/32-batony-klasyczne") == "category"
    assert url_kind(f"{BASE}/strona/1-regulamin-sklepu") is None
    assert url_kind(f"{BASE}/") is None


def test_stara_domena_zamieniana_na_sklep():
    assert same_host("https://www.dobrakaloria.e-prestacart.pl/sitemap-products.xml", BASE) == \
        f"{BASE}/sitemap-products.xml"


def test_indeks_jest_rozwijany_a_adresy_rozdzielone():
    wynik = collect_sitemap_urls(FakeFetcher(STRONY), [f"{BASE}/sitemap.xml"], BASE)
    assert wynik["products"] == [
        f"{BASE}/batony-klasyczne/30-baton-chrupiacy-orzech-35-g",
        f"{BASE}/batony-klasyczne/36-baton-nerkowce-kokos-35-g",   # duplikat usunięty
    ]
    assert wynik["categories"] == [f"{BASE}/32-batony-klasyczne", f"{BASE}/55-zdrowe-sniadanie"]


def test_brakujaca_sitemapa_nie_przerywa():
    wynik = collect_sitemap_urls(FakeFetcher(STRONY), [f"{BASE}/nie-ma.xml", f"{BASE}/sitemap-products.xml"], BASE)
    assert len(wynik["products"]) == 2


def test_sitemapy_z_robots_txt():
    fetcher = FakeFetcher(STRONY, sitemaps=[f"{BASE}/sitemap.xml"])
    wynik = load_sitemap_urls(fetcher, BASE)
    assert len(wynik["products"]) == 2 and len(wynik["categories"]) == 2


def test_zapasowe_adresy_gdy_robots_bez_sitemap():
    fetcher = FakeFetcher(STRONY, sitemaps=[])
    wynik = load_sitemap_urls(fetcher, BASE)
    assert len(wynik["products"]) == 2
    assert f"{BASE}/sitemap-products.xml" in fetcher.pobrane
