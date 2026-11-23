"""Testy przebiegu kategorie -> produkty -> walidacja; FakeFetcher serwuje strony z fixtures/."""

import logging
from pathlib import Path

from main import (
    apply_manual_categories,
    build_categories,
    collect_product_urls,
    drop_unknown_extra_categories,
    find_missing,
    scrape_products,
)

FIXTURES = Path(__file__).parent / "fixtures"

URL_A = "https://dobrakaloria.pl/batony-proteinowe/237-mini-batoniki"
URL_B = "https://dobrakaloria.pl/batony-klasyczne/36-baton-nerkowce-kokos-35-g"
URL_B_INNA_SCIEZKA = "https://dobrakaloria.pl/wszystkie-produkty/36-baton-nerkowce-kokos-35-g"
URL_ZEPSUTY = "https://dobrakaloria.pl/zestawy/999-to-nie-jest-produkt"



def kategoria_html(*adresy, nastepna=None):
    """Najmniejsza możliwa strona kategorii z podanymi produktami (i linkiem do następnej strony)."""
    kafelki = "".join(f'<article class="product-miniature"><a href="{a}">x</a></article>' for a in adresy)
    link = f'<a rel="next" href="{nastepna}">dalej</a>' if nastepna else ""
    return f'<div id="js-product-list">{kafelki}{link}</div>'



class FakeFetcher:
    def __init__(self):
        self.network_requests = 0
        self.strony = {
            # duża podkategoria zbiorcza, jak "Mini batoniki - 6 sztuk"
            "https://kat/wszystkie": kategoria_html(URL_A, URL_B, URL_ZEPSUTY),
            "https://kat/proteinowe": kategoria_html(URL_A),
            "https://kat/kokos": kategoria_html(URL_B_INNA_SCIEZKA),  # ten sam B, inny adres
            # podkategoria na 2 stronach
            "https://kat/dwie-strony": kategoria_html(URL_A, nastepna="https://kat/dwie-strony?page=2"),
            "https://kat/dwie-strony?page=2": kategoria_html(URL_B),
            "https://kat/pozostale": kategoria_html(URL_A, URL_B),
            # pełna lista sklepu z produktem 555 spoza naszych podkategorii
            "https://kat/caly-sklep": kategoria_html(URL_A, URL_B, "https://dobrakaloria.pl/x/555-zgubiony"),
            URL_A: (FIXTURES / "product_simple.html").read_text(encoding="utf-8"),
            URL_B: (FIXTURES / "product_many_images.html").read_text(encoding="utf-8"),
            URL_ZEPSUTY: (FIXTURES / "category.html").read_text(encoding="utf-8"),  # nie-produkt
        }

    def get(self, url):
        return self.strony[url]


DRZEWO = {"Batony": {
    "Wszystkie": "https://kat/wszystkie",
    "Proteinowe": "https://kat/proteinowe",
    "Kokos": "https://kat/kokos",
}}


def test_duplikaty_po_id_sa_pomijane():
    znalezione = collect_product_urls(FakeFetcher(), DRZEWO)
    assert sorted(znalezione) == [36, 237, 999]  # każde ID raz, choć 36 i 237 były w 2 kategoriach


def test_produkt_trafia_do_najmniejszej_podkategorii():
    znalezione = collect_product_urls(FakeFetcher(), DRZEWO)
    assert znalezione[237][1] == ["Batony", "Proteinowe"]  # 1 produkt < 3 produkty w "Wszystkie"
    assert znalezione[36][1] == ["Batony", "Kokos"]
    assert znalezione[999][1] == ["Batony", "Wszystkie"]   # jest tylko tam


def test_kategorie_dodatkowe():
    znalezione = collect_product_urls(FakeFetcher(), DRZEWO)
    assert znalezione[237][2] == [["Batony", "Wszystkie"]]   # domyślna: Proteinowe, dodatkowo: Wszystkie
    assert znalezione[999][2] == []


def test_kategorie_dodatkowe_w_wyniku():
    fetcher = FakeFetcher()
    produkty, _ = scrape_products(fetcher, collect_product_urls(fetcher, DRZEWO))
    p = next(p for p in produkty if p["id"] == 237)
    assert p["category_path"] == ["Batony", "Proteinowe"]
    assert p["extra_categories"] == [["Batony", "Wszystkie"]]


def test_brakujace_z_sitemapy():
    fetcher = FakeFetcher()
    znalezione = collect_product_urls(fetcher, DRZEWO)
    brakujace = find_missing(fetcher, "https://kat/caly-sklep", znalezione,
                             ["https://dobrakaloria.pl/x/888-tylko-w-sitemapie"])
    assert "https://dobrakaloria.pl/x/888-tylko-w-sitemapie" in brakujace


def test_wykrywa_produkty_poza_naszymi_kategoriami():
    fetcher = FakeFetcher()
    znalezione = collect_product_urls(fetcher, DRZEWO)
    assert find_missing(fetcher, "https://kat/caly-sklep", znalezione) == ["https://dobrakaloria.pl/x/555-zgubiony"]


def test_reczne_przypisanie_kategorii():
    znalezione = {}
    zostaly = apply_manual_categories(
        znalezione,
        ["https://dobrakaloria.pl/x/555-zgubiony", "https://dobrakaloria.pl/x/777-inny"],
        {555: ["Zestawy słodyczy", "Pozostałe zestawy słodyczy"]},
    )
    assert znalezione == {
        555: ("https://dobrakaloria.pl/x/555-zgubiony", ["Zestawy słodyczy", "Pozostałe zestawy słodyczy"], [])
    }
    assert zostaly == ["https://dobrakaloria.pl/x/777-inny"]  # bez ręcznej kategorii -> dalej brakuje


def test_zepsuty_produkt_jest_odrzucony_a_reszta_zapisana():
    fetcher = FakeFetcher()
    produkty, bledy = scrape_products(fetcher, collect_product_urls(fetcher, DRZEWO))
    assert len(produkty) == 2
    assert bledy == 1
    assert {p["id"] for p in produkty} == {36, 237}


def test_lista_kategorii_bez_pustych():
    fetcher = FakeFetcher()
    produkty, _ = scrape_products(fetcher, collect_product_urls(fetcher, DRZEWO))
    kategorie = build_categories(produkty)
    podkategorie = {s["name"]: s["products"] for s in kategorie[0]["subcategories"]}
    # "Wszystkie" zawierała tylko odrzucony produkt, więc nie ma jej w wyniku
    assert podkategorie == {"Proteinowe": 1, "Kokos": 1}


def test_paginacja_podkategorii():
    znalezione = collect_product_urls(FakeFetcher(), {"Batony": {"Dwie strony": "https://kat/dwie-strony"}})
    assert sorted(znalezione) == [36, 237]                   # produkt z 2. strony też jest


def test_pozostale_nie_sa_kategoria_dodatkowa():
    drzewo = {"Batony": {"Proteinowe": "https://kat/proteinowe", "Pozostałe batony": "https://kat/pozostale"}}
    znalezione = collect_product_urls(FakeFetcher(), drzewo)
    assert znalezione[237][1] == ["Batony", "Proteinowe"]
    assert znalezione[237][2] == []                          # "Pozostałe ..." to strona całej kategorii


def test_remis_rozstrzyga_kolejnosc_w_config():
    # produkt 36 jest w dwóch podkategoriach po 1 produkcie: wygrywa pierwsza w config.py
    drzewo = {"Batony": {"Kokos": "https://kat/kokos", "Klasyczne": "https://kat/kokos"}}
    znalezione = collect_product_urls(FakeFetcher(), drzewo)
    assert znalezione[36][1] == ["Batony", "Kokos"]
    assert znalezione[36][2] == [["Batony", "Klasyczne"]]


def test_kolejnosc_kategorii_jak_w_config():
    produkty = [{"category_path": ["B", "b2"]}, {"category_path": ["A", "a1"]}, {"category_path": ["B", "b1"]}]
    kategorie = build_categories(produkty, {"A": {"a1": ""}, "B": {"b1": "", "b2": ""}})
    assert [k["name"] for k in kategorie] == ["A", "B"]
    assert [s["name"] for s in kategorie[1]["subcategories"]] == ["b1", "b2"]


def test_dodatkowe_tylko_do_istniejacych_kategorii():
    produkty = [
        {"category_path": ["Batony", "Proteinowe"], "extra_categories": [["Batony", "Kokos"], ["Batony", "Worek"]]},
        {"category_path": ["Batony", "Kokos"], "extra_categories": []},
    ]
    drop_unknown_extra_categories(produkty, build_categories(produkty))
    assert produkty[0]["extra_categories"] == [["Batony", "Kokos"]]   # "Worek" nie ma w categories.json


def test_pominiete_celowo_nie_sa_ostrzezeniem(caplog):
    caplog.set_level(logging.INFO, logger="scraper")
    znalezione = {237: ("u", ["Batony", "Proteinowe"], [])}
    brakujace = find_missing(FakeFetcher(), "https://kat/kokos", znalezione, pominiete={36: "Torba"})
    assert brakujace == []                                   # produkt 36 pominięty świadomie
    assert "pominięty celowo" in caplog.text
    assert "poza naszymi kategoriami" not in caplog.text
