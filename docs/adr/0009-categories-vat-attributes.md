# ADR 0009: Kategorie, VAT i atrybuty

- **Status:** zaakceptowana
- **Data:** 2026-11-12

## Kontekst

Wymagania: ≥ 4 kategorie, każda z ≥ 2 niepustymi podkategoriami (W3), a ceny i stawki VAT
mają odpowiadać źródłu. Sklep źródłowy:
- ma menu 3-poziomowe, a ten sam produkt bywa w kilku podkategoriach naraz,
- część podkategorii to „worki” (np. *Mini batoniki - 6 sztuk*: 30 produktów), które zawierają produkty z innych,
- część to kategorie marketingowe i tymczasowe (Nowości, Bestsellery, Promocje, Polecane, a pod
  *Zamiennikami mięsa* także *Promocje z krótką datą*, gdzie trafiają też słodycze),
- **zestawy** łączą produkty o różnych stawkach VAT (np. batony 5% i 23%), więc wyliczona
  stawka wychodzi np. 8,5%, a takiej stawki w Polsce nie ma,
- nie ma cech typu kolor/rozmiar.

## Rozważane opcje

**Kategorie**
1. Pierwsza podkategoria, w której scraper znalazł produkt. Sprawdzone: „worki” zgarniały
   wszystko, *Mini batoniki* miały 1 niepustą podkategorię, więc warunek W3 niespełniony.
2. Kategoria z okruszków (breadcrumb) strony. Często „Wszystkie produkty”, czyli bezużyteczne.
3. **Najmniejsza podkategoria, w której produkt występuje w źródle.**

**Kategorie marketingowe i tymczasowe**
1. Zostawić jak zwykłe podkategorie. Sprawdzone: *Promocje z krótką datą* (14 produktów) zabierała
   produkty jako mniejsza od *O smaku ciast* (15), więc mini batonik trafiał do *Zamienników mięsa*.
2. Zostawić z najniższym priorytetem przy wyborze kategorii domyślnej. Kategoria i tak zmienia się
   z dnia na dzień, więc w naszym sklepie byłaby myląca.
3. **Pominąć, tak jak Nowości i Promocje.**

**VAT dla zestawów**
1. Stawka „mieszana” (np. 8,5%). PrestaShop jej nie przyjmie (reguła podatkowa = jedna stawka).
2. Brak stawki. Import musiałby zgadywać.
3. **Najbliższa prawdziwa stawka (0/5/8/23%) przy niezmienionej cenie brutto.**

## Decyzja

- Kategorie = nagłówki kolumn menu źródła, podkategorie = linki pod nimi (`scraper/config.py`).
- Produkt trafia do **najmniejszej** podkategorii, w której jest w źródle (odpowiednik
  „kategorii domyślnej” w PrestaShop). Podkategorie „Pozostałe …” (strona całej kategorii)
  łapią produkty spoza mniejszych podkategorii.
- Nowości, Bestsellery, Promocje, Polecane i *Promocje z krótką datą* są pominięte.
- Pozostałe podkategorie, w których produkt występuje, zapisujemy jako `extra_categories`
  (dodatkowe powiązania w PrestaShop), ale tylko te, które są w `categories.json`; „worki”
  i „Pozostałe …” nie są dodatkowymi kategoriami.
- Scraper porównuje wynik z listą „Wszystkie produkty” i z sitemapą produktów i ostrzega w logu
  o każdym zgubionym produkcie. Takie produkty przypisujemy ręcznie w `MANUAL_CATEGORIES` (ID 134).
  Produkty, które nie są jedzeniem (torby, ID 334 i 335), są świadomie pominięte w `EXCLUDED_PRODUCTS`.
- VAT = najbliższa stawka z 0/5/8/23%. Dotyczy 4 zestawów, każdy przypadek jest w logu jako ostrzeżenie.
  Rozwiązanie tymczasowe, uzgodnione w review #22: sprawa jest zgłoszona prowadzącemu,
  a jeśli zdecyduje inaczej, zmienimy VAT w scraperze i w imporcie.
- Atrybuty: *Gramatura* (z nazwy), *Składniki*, *Wartość energetyczna (100 g)*, *Cechy*
  (wyróżniki pod opisem), a dla zestawów *Zawartość zestawu*.

## Konsekwencje

- 141 produktów (wszystkie ze sklepu poza 2 torbami), 7 kategorii, każda ma ≥ 3 niepuste podkategorie, 0 pustych.
- **Import musi ustawiać cenę brutto** (a nie netto), żeby cena zestawów zgadzała się ze źródłem co do grosza.
- Nowy produkt spoza podkategorii pojawi się w logu jako ostrzeżenie i trzeba go dopisać w `config.py`.
