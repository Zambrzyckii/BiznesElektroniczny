"""Testy walidacji schematem i podsumowania przebiegu."""

import logging
from pathlib import Path

import pytest

from parsers import parse_product
from validation import log_summary, validate_product

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://dobrakaloria.pl/batony-proteinowe/237-mini-batoniki"


def wczytaj(nazwa):
    return (FIXTURES / nazwa).read_text(encoding="utf-8")


@pytest.mark.parametrize("plik", [
    "product_simple.html",
    "product_many_images.html",
    "product_promo.html",
    "product_unavailable.html",
    "product_gift_links.html",
    "product_gift_box.html",
])
def test_kazdy_zapisany_produkt_przechodzi_walidacje(plik):
    assert validate_product(parse_product(wczytaj(plik)), URL) is not None


@pytest.mark.parametrize("pole, wartosc", [
    ("images", []),          # bez zdjęć
    ("name", ""),            # bez nazwy
    ("description", ""),     # bez opisu
    ("price_gross", 0),      # cena 0
    ("name", "   "),         # nazwa z samych spacji
])
def test_niekompletny_produkt_odrzucony_z_adresem_w_logu(pole, wartosc, caplog):
    dane = parse_product(wczytaj("product_simple.html"))
    dane[pole] = wartosc
    with caplog.at_level(logging.ERROR, logger="scraper"):
        assert validate_product(dane, URL) is None
    assert URL in caplog.text and pole in caplog.text


def test_pole_spoza_schematu_odrzucone(caplog):
    # zapomniane pole w models.py ma dać błąd w logu, a nie zniknąć po cichu
    dane = parse_product(wczytaj("product_simple.html"))
    dane["kalorie"] = 120
    with caplog.at_level(logging.ERROR, logger="scraper"):
        assert validate_product(dane, URL) is None
    assert "kalorie" in caplog.text


class FakeFetcher:
    network_requests = 3
    cache_hits = 12


def test_podsumowanie(caplog):
    with caplog.at_level(logging.INFO, logger="scraper"):
        log_summary(10, 2, FakeFetcher())
    assert "10 produktów zapisanych, 2 odrzuconych" in caplog.text
    assert "3 zapytań do sieci, 12 stron z cache" in caplog.text
