# Analiza sklepu źródłowego dobrakaloria.pl

Stan na 25.10.2026. Sklep działa na PrestaShop (motyw e-Presta); strony są renderowane
po stronie serwera, więc dane są w HTML bez wykonywania JavaScriptu.

## Skąd brać pola wymagane w W2

Karta produktu zawiera blok JSON-LD `Product` (`<script type="application/ld+json">`)
oraz meta tagi Open Graph `product:*`.

| Pole | Źródło na karcie produktu | Uwagi |
|---|---|---|
| nazwa | JSON-LD `Product.name` | część tekstów ma podwójnie zakodowane encje (`&amp;`), trzeba je odkodować |
| opis | JSON-LD `Product.description` | ten sam tekst co sekcja „Opis produktu” (`#product-description-short-<id>`) |
| cena brutto | JSON-LD `offers.price` | bywa z 4 miejscami po przecinku (np. 44.8455), więc zaokrąglamy do groszy |
| cena przed obniżką | meta `product:price:standard_amount` | tylko przy promocjach |
| najniższa cena z 30 dni | tekst „Najniższa cena z 30 dni: X pln” w `.product-information` | tylko przy promocjach (Omnibus) |
| **stawka VAT** | **brak wprost**; wyliczana: `offers.price` / meta `product:pretax_price:amount` − 1 | zob. sekcję VAT |
| waga | JSON-LD `weight.value` (kg), też meta `product:weight:value` | brak u 4 produktów (2 zestawy, kalendarz adwentowy, baton Energia 45 g) |
| atrybuty | brak cech typu kolor/rozmiar; z tekstu strony: gramatura (z nazwy), „Składniki:” i wartość energetyczna (zakładka `#tabdesc`), wyróżniki `ul.fetaures-top`, zawartość zestawu (`#ap5-product-list` albo linki w `#tabdesc`) | skład ma 103 ze 137 produktów, wartość energetyczną 101, zawartość zestawu 40 |
| zdjęcia | JSON-LD `offers.image` (lista całej galerii) | rozmiar `large_default`: 848×1200 px; `Product.image` daje tylko pierwsze zdjęcie, meta `og:image` powtarza całą galerię (źródło zapasowe) |
| dostępność | JSON-LD `offers.availability` (`InStock` / `OutOfStock`) | meta `og:availability` jest zawsze `instock`, więc się nie nadaje |
| kategoria | JSON-LD `BreadcrumbList` | okruszki to często „Wszystkie produkty”; kategorię bierzemy z drzewa poniżej |

Lista produktów w kategorii: kafelki `#js-product-list .product-miniature`, paginacja
`?page=N`, link `a[rel="next"]`. Menu na górze strony też zawiera kafelki produktów,
więc trzeba czytać tylko `#js-product-list`.

robots.txt blokuje m.in. `?order=`, `?n=`, `search_query`, koszyk i konto; karty produktów,
kategorie, paginacja, zdjęcia i sitemapy są dozwolone. Reguły używają `*`,
czego nie obsługuje `urllib.robotparser`.

## VAT

Strona nie podaje stawki VAT wprost. Podaje cenę brutto (JSON-LD) i netto (meta
`product:pretax_price:amount`), więc stawka = brutto / netto − 1:

| Stawka | Produkty |
|---|---|
| 5% | 90 |
| 8% | 31 (w tym 3 zestawy ze stawką mieszaną) |
| 23% | 16 |

Trzy **zestawy** łączą produkty o różnych stawkach i wychodzi z nich stawka mieszana
(8,5–10,8%). Przyjmujemy najbliższą obowiązującą (8%) przy niezmienionej cenie brutto.
Szczegóły i konsekwencje dla importu opisze ADR „Kategorie, VAT i atrybuty” (dochodzi w #23).

Zgodnie z #22 sprawa VAT jest zgłoszona prowadzącemu; jego odpowiedź zapiszemy w komentarzu w #22.

## Zdjęcia

137 produktów, każdy ma co najmniej 1 zdjęcie; **97 produktów ma co najmniej 2**.

| Liczba zdjęć | 1 | 2 | 3 | 4 | 5–11 |
|---|---|---|---|---|---|
| Produkty | 40 | 59 | 14 | 7 | 17 |

## Kategorie

Menu źródła ma 3 poziomy i zawiera kategorie marketingowe (Nowości, Bestsellery, Polecane,
Promocje) oraz zbiorcze (np. „Wszystkie batony”, „Mini batoniki - 6 sztuk”, 30 produktów).
Ten sam produkt występuje w kilku podkategoriach.

Proponowane drzewo: kategoria = kolumna menu, podkategoria = link pod nią. Marketingowe
są pominięte. Wyjątek do decyzji zespołu: „Promocje z krótką datą” jest w menu pod
„Zamiennikami mięsa”, ale to kategoria tymczasowa i trafiają do niej też słodycze
(np. mini batonik à la rogal poznański); albo ją pomijamy, albo dajemy jej najniższy
priorytet przy wyborze kategorii domyślnej (wdrożenie w #23). Produkt ma kategorię domyślną w najmniejszej podkategorii, w której
występuje, a pozostałe jako dodatkowe powiązania. „Pozostałe …” to strona całej kategorii
dla produktów spoza mniejszych podkategorii. Liczby produktów wg kategorii domyślnej:

| Kategoria | Podkategorie (produkty) |
|---|---|
| Batony | Daktyle w posypce (4), Batony z dodatkiem kokosa (2), Batony z dodatkiem czekolady (2), Batony klasyczne (2), Batony proteinowe (6), Batony z nerkowców (6), Pozostałe batony (2) |
| Mini batoniki | O smaku ciast (14), O smaku deserów (3), Do zadań specjalnych (4), Proteinowe z niskim IG (3), O smaku kultowych batonów (3), Klasyczne smaki (2) |
| Kulki | Kulki RAW z kakao (7), Kulki zbożowe (4), Kulki w pudrze owocowym (2), Pozostałe kulki (1) |
| Zdrowe śniadanie | Produkty śniadaniowe (7), Przekąski śniadaniowe (4), Kremy orzechowe (3) |
| Zamienniki mięsa | Szybkie obiady (6), Promocje z krótką datą (7), Burgery (6), Kiełbaski, parówki i kaszanki (5), Zdrowy grill (1), Pasztety (1) |
| Zestawy słodyczy | W zestawie taniej (21), Na prezent (2), Pozostałe zestawy słodyczy (2) |
| Zestawy niemięs | Średni (3), Duży (1), Pozostałe zestawy niemięs (1) |

7 kategorii, każda z co najmniej 3 niepustymi podkategoriami. Lista „Wszystkie produkty”
ma 137 produktów; jeden (ID 134) nie należy do żadnej podkategorii i jest przypisany
ręcznie (`MANUAL_CATEGORIES` w `scraper/config.py`).

## Inne dane przydatne dalej

- 19 produktów jest niedostępnych w źródle (14%).
- 62 produkty mają cenę przed obniżką (promocje).
