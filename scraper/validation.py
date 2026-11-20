"""Walidacja produktów schematem (models.Product) i podsumowanie przebiegu scrapera."""

import logging

from pydantic import ValidationError

from models import Product

log = logging.getLogger("scraper")


def validate_product(dane, url):
    """Słownik z parsera -> słownik zgodny ze schematem albo None; błąd trafia do logu z adresem produktu."""
    try:
        return Product.model_validate(dane).model_dump(mode="json")
    except ValidationError as e:
        log.error("Produkt %s nie przeszedł walidacji:\n%s", url, e)
        return None


def log_summary(zapisane, odrzucone, fetcher, poza_kategoriami=0):
    """Podsumowanie: rekordy poprawne i odrzucone oraz ile stron pobrano, a ile wzięto z cache (wznowienie).

    poza_kategoriami: produkty ze sklepu bez kategorii w naszym drzewie (liczy main.py, #23).
    Liczba zapytań do sieci nie obejmuje robots.txt, pobieranego przy każdym uruchomieniu.
    """
    log.info("KONIEC: %d produktów zapisanych, %d odrzuconych, %d poza kategoriami, "
             "%d zapytań do sieci, %d stron z cache (pobranych wcześniej)",
             zapisane, odrzucone, poza_kategoriami, fetcher.network_requests, fetcher.cache_hits)
