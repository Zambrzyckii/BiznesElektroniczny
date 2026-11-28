# ADR 0010: Przechowywanie zdjęć

- **Status:** zaakceptowana
- **Data:** 2026-11-16

## Kontekst

369 zdjęć 141 produktów (dłuższy bok 800–1600 px, ≤ 300 kB), razem ok. 50 MB. Wymagania:
zdjęć nie trzymamy w repozytorium ani w Git LFS, repo ≤ 200 MB, a skrypt inicjalizacji
danych ma działać z czystego klona (≤ 15 min), także na klastrze w etapie 2.

## Rozważane opcje

| Opcja | Zalety | Wady |
|---|---|---|
| zdjęcia w repo | najprostsze, wszystko w jednym klonie | zabronione przez wymagania; puchnie historia gita |
| Git LFS | pliki wersjonowane razem z kodem | zabronione przez wymagania; darmowy limit transferu łatwo przekroczyć |
| **zip w GitHub Releases + zapasowo adresy źródłowe (wybrana)** | zgodne z wymaganiami, jedno pobranie, darmowe | po każdym scrapowaniu trzeba wrzucić nowy zip |
| zewnętrzny dysk/chmura | bez limitów GitHuba | dodatkowe konto i dane dostępowe (sekrety) |

## Decyzja

- `scraper/images.py` zapisuje gotowe zdjęcia jako `scraper/images/<id>-<nr>.jpg`
  (folder w `.gitignore`), a `scraper-results/images.json` podaje dla każdego zdjęcia
  plik lokalny i adres źródłowy.
- `scraper/archive.py` pakuje zdjęcia wymienione w `images.json` do `scraper/images.zip`
  (pliki `<id>-<nr>.jpg` w głównym katalogu archiwum; sprawdza limit 1 GB)
  i kopiuje do 20 przykładów do `scraper-results/sample-images/`, które trafiają do repo.
- `images.zip` dołączamy do Release w zakładce Releases repozytorium, przed tagiem `etap1`.

## Konsekwencje

- Skrypt inicjalizacji danych (#17) może pobrać `images.zip` z Releases; zdjęcia da się też
  odtworzyć z adresów w `products.json` przez `scraper/images.py`. Sposób wybiera #17.
- Po każdym ponownym scrapowaniu trzeba wrzucić nowy `images.zip` do Releases.
- Obraz kontenera nie zawiera zdjęć, więc jest mały i bezstanowy (ważne dla Swarma w etapie 2).
