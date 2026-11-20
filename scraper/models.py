"""Schemat produktu w scraper-results/products.json (kontrakt ze skryptem importu).

Rekord niezgodny ze schematem (np. bez nazwy, z ceną 0, bez zdjęć, z polem spoza schematu)
powoduje ValidationError; validation.py zapisuje błąd w logu, a main.py (#23) pomija rekord.
Nowe pole produktu = nowa linijka tutaj, inaczej rekord zostanie odrzucony (a nie po cichu obcięty).
"""

from typing import Optional  # zamiast "X | None" dla zgodności z Pythonem 3.9

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Product(BaseModel):
    # extra="forbid": pole spoza schematu to błąd; str_strip_whitespace: nazwa ze spacji = pusta nazwa
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: int
    source_url: HttpUrl
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    price_gross: float = Field(gt=0)                # PLN
    old_price_gross: Optional[float] = None         # cena przed obniżką (promocje)
    lowest_price_30d: Optional[float] = None        # Omnibus (promocje)
    vat_rate: Optional[int] = None                  # %
    weight_kg: Optional[float] = None
    available: bool
    category_path: list[str] = Field(min_length=1)  # np. ["Zestawy słodyczy", "Na prezent"]
    extra_categories: list[list[str]] = []          # dodatkowe powiązania z kategoriami
    attributes: dict[str, str] = {}
    images: list[HttpUrl] = Field(min_length=1)     # adresy źródłowe, kolejność jak w galerii
