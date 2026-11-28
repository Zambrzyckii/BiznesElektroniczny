# Scraper dobrakaloria.pl

Pobiera kategorie, produkty i zdjęcia ze sklepu dobrakaloria.pl (wyłącznie do celów dydaktycznych)
i zapisuje je w `../scraper-results/` jako JSON w UTF-8.

## Moduły

| Plik | Odpowiedzialność |
|---|---|
| `config.py` | adres sklepu i drzewo kategorii |
| `fetcher.py` | pobieranie: tempo ≤ 2 zapytania/s, robots.txt, User-Agent, cache (wznawianie) |
| `sitemap.py` | adresy wszystkich produktów i kategorii z sitemap sklepu |
| `parsers.py` | HTML → dane (bez sieci) |
| `models.py` | schemat produktu (pydantic) |
| `validation.py` | walidacja schematem, błędy w logu, podsumowanie przebiegu |
| `main.py` | sitemapy, kategorie → produkty → walidacja → `sitemap.json`, `products.json`, `categories.json` |
| `images.py` | zdjęcia: dłuższy bok 800–1600 px, JPEG ≤ 300 KB, `images.json` |
| `archive.py` | `images.zip` do Releases (zdjęcia z `images.json`) i 20 przykładów do repo |
| `tests/` | testy jednostkowe na stronach zapisanych w `tests/fixtures/`; `test_wyniki.py` sprawdza zapisane wyniki pod kątem W2 |

## Uruchomienie

Python 3.9+, w folderze `scraper/`:

```
python -m pip install -r requirements.txt
python -m pytest
python -m ruff check .
python sitemap.py   # opcjonalnie: same sitemapy; main.py też je pobiera
python main.py
python images.py
python archive.py
```

- log z czasem każdego zapytania: `logs/scraper.log`, `logs/images.log`; archiwum: `logs/archive.log`
- po przerwaniu (Ctrl+C) ponowne uruchomienie korzysta z `cache/` i gotowych plików w `images/`
- pełne pobranie od nowa: usuń `cache/` i `images/`

## Wyniki

| Plik | Zawartość |
|---|---|
| `products.json` | produkty: nazwa, opis, cena brutto, cena przed obniżką, najniższa cena z 30 dni, VAT, waga, dostępność, kategoria domyślna i dodatkowe, atrybuty, adresy źródłowe zdjęć |
| `categories.json` | kategorie i niepuste podkategorie z liczbą produktów |
| `sitemap.json` | adresy produktów i kategorii z sitemap sklepu |
| `images.json` | dla każdego zdjęcia: plik lokalny (`<id>-<nr>.jpg`, 1 = główne) i adres źródłowy |
| `sample-images/` | 20 przykładowych zdjęć; pełny zbiór: `images.zip` w Releases |

Skrypt importu powinien ustawiać **cenę brutto** (`docs/adr/0009-categories-vat-attributes.md`).

## Publikacja wyników

1. W `scraper/`: `python main.py`, potem `python images.py`, potem `python archive.py`.
2. Commit odświeżonych plików z `scraper-results/` (JSON-y i `sample-images/`; reszta folderu jest w `.gitignore`).
3. `scraper/images.zip` do Release w zakładce Releases repozytorium (przed tagiem `etap1`),
   np. `gh release upload etap1 scraper/images.zip --clobber`.

Archiwum ma pliki `<id>-<nr>.jpg` w głównym katalogu; rozpakowanie do `scraper/images/` odtwarza
stan po `images.py`, a `images.json` łączy każdy plik z produktem i adresem źródłowym.

## Decyzje dotyczące danych

Szczegóły w `docs/adr/0009-categories-vat-attributes.md`.

| Decyzja | Powód |
|---|---|
| kategorie = kolumny menu sklepu, podkategorie = linki pod nimi | menu źródła ma 3 poziomy |
| produkt z kilku podkategorii → domyślna = najmniejsza, reszta jako dodatkowe | podkategorie zbiorcze zostawiały pozostałe puste |
| „Pozostałe …” = strona całej kategorii | produkty spoza mniejszych podkategorii |
| kategorie marketingowe i „Promocje z krótką datą” pominięte | tymczasowe filtry; mini batonik trafiał do zamienników mięsa |
| `extra_categories` tylko do kategorii z `categories.json` | import nie ma do czego przypiąć „worków” |
| kontrola z listą „Wszystkie produkty” i sitemapą | ostrzeżenie w logu o produkcie spoza drzewa kategorii |
| `MANUAL_CATEGORIES` | produkt 134 nie należy w źródle do żadnej podkategorii |
| VAT → najbliższa stawka z 0/5/8/23% | zestawy łączą produkty o różnych stawkach; cena brutto bez zmian |
| atrybuty: gramatura (z nazwy), skład, wartość energetyczna, cechy, zawartość zestawu | sklep nie ma cech typu kolor/rozmiar |

## Typowe problemy

| Objaw | Rozwiązanie |
|---|---|
| `'pytest' is not recognized` | `python -m pytest` |
| `No module named ...` | `python -m pip install -r requirements.txt` tym samym `python` |
