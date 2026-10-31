# ADR 0001: Biblioteka do scrapowania

- **Status:** zaakceptowana
- **Data:** 2026-10-25

## Kontekst

Scraper ma pobrać kategorie i produkty ze sklepu dobrakaloria.pl (PrestaShop),
respektując robots.txt, ograniczając tempo do ≤ 2 zapytań/s, z możliwością
wznowienia po przerwaniu i z testami na zapisanych stronach HTML (wymaganie W2).

Rozpoznanie sklepu:
- strony są renderowane po stronie serwera: cena, opis i zdjęcia są w HTML, bez JavaScriptu,
- każda karta produktu zawiera blok **JSON-LD** (`<script type="application/ld+json">`)
  z nazwą, opisem, ceną brutto, dostępnością, wagą i listą wszystkich zdjęć,
- robots.txt używa reguł z gwiazdką, np. `Disallow: /*?order=`.

## Rozważane opcje

| Opcja | Zalety | Wady |
|---|---|---|
| **requests + BeautifulSoup** | proste, łatwe do zrozumienia i testowania, wystarczy dla HTML z serwera | tempo, cache i wznawianie trzeba napisać samemu |
| Scrapy | gotowe tempo, robots.txt, kolejki | duży framework, więcej konwencji niż potrzeba przy ok. 140 produktach |
| Playwright | obsługuje strony renderowane w JS | prawdziwa przeglądarka: wolno i ciężko, a tu niepotrzebne |

Do robots.txt rozważaliśmy wbudowany `urllib.robotparser`, ale **nie obsługuje on
gwiazdki `*`**, więc reguła `Disallow: /*?order=` byłaby ignorowana.

## Decyzja

- **requests** do pobierania, **BeautifulSoup** do czytania HTML,
- dane produktu z **JSON-LD** (zwykły JSON, odporny na zmiany wyglądu strony),
  cena netto z meta tagu `product:pretax_price:amount` (do wyliczenia VAT),
- **protego** do robots.txt (obsługuje `*`, ta sama biblioteka, której używa Scrapy),
- **pydantic** do walidacji schematu produktu,
- **Pillow** do skalowania zdjęć.

## Konsekwencje

- Tempo (0,6 s między zapytaniami), User-Agent i cache na dysku (wznawianie)
  są we własnym `fetcher.py`, pokryte testami bez internetu.
- Parsery nie łączą się z siecią, więc testy działają na `tests/fixtures/*.html` i w CI.
- Jeśli sklep źródłowy przejdzie na renderowanie w JavaScripcie, trzeba będzie
  wymienić `fetcher.py` na Playwright. Parsery mogą zostać, bo dostają gotowy HTML.
