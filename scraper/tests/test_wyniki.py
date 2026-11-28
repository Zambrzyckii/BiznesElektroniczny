"""Sprawdzenie zapisanych wyników scrapera (scraper-results/) pod kątem W2.

Pliki wyników są w repo od #27; bez nich (np. na gałęzi przed #27) testy są pomijane.
"""

import io
import json
from pathlib import Path

import pytest
from PIL import Image

from images import MAX_BYTES, MAX_SIDE, MIN_SIDE
from models import Product

WYNIKI = Path(__file__).resolve().parents[2] / "scraper-results"


def wczytaj(nazwa):
    plik = WYNIKI / nazwa
    if not plik.exists():
        pytest.skip(f"brak {plik} (wyniki trafiają do repo w #27)")
    return json.loads(plik.read_text(encoding="utf-8"))


def test_kazdy_produkt_zgodny_ze_schematem():
    produkty = wczytaj("products.json")
    for p in produkty:
        Product.model_validate(p)
    assert len({p["id"] for p in produkty}) == len(produkty)          # bez duplikatów


def test_co_najmniej_50_produktow_z_dwoma_zdjeciami():
    assert sum(len(p["images"]) >= 2 for p in wczytaj("products.json")) >= 50


def test_spis_zdjec_zgodny_z_produktami():
    produkty = {str(p["id"]): p["images"] for p in wczytaj("products.json")}
    spis = wczytaj("images.json")
    assert set(spis) == set(produkty)                                 # każdy produkt ma zdjęcie
    for pid, zdjecia in spis.items():
        assert [z["source_url"] for z in zdjecia] == produkty[pid]
        assert [z["file"] for z in zdjecia] == [f"{pid}-{n}.jpg" for n in range(1, len(zdjecia) + 1)]


def test_kategorie_spelniaja_w3():
    kategorie = wczytaj("categories.json")
    assert len(kategorie) >= 4
    for k in kategorie:
        assert sum(s["products"] > 0 for s in k["subcategories"]) >= 2, k["name"]
    istniejace = {(k["name"], s["name"]) for k in kategorie for s in k["subcategories"]}
    for p in wczytaj("products.json"):
        assert tuple(p["category_path"]) in istniejace
        assert all(tuple(e) in istniejace for e in p["extra_categories"])


def test_przykladowe_zdjecia():
    folder = WYNIKI / "sample-images"
    if not folder.exists():
        pytest.skip("brak sample-images (trafiają do repo w #27)")
    pliki = sorted(folder.glob("*.jpg"))
    assert 1 <= len(pliki) <= 20
    for plik in pliki:
        dane = plik.read_bytes()
        obraz = Image.open(io.BytesIO(dane))
        assert obraz.format == "JPEG", plik.name
        assert len(dane) <= MAX_BYTES, plik.name
        assert MIN_SIDE <= max(obraz.size) <= MAX_SIDE, plik.name
