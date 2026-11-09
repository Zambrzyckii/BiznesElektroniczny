"""Konfiguracja scrapera: adres sklepu i drzewo kategorii (ADR „Kategorie, VAT i atrybuty”).

Kategorie to nagłówki kolumn menu sklepu źródłowego, podkategorie to linki pod nimi.
"Pozostałe ..." wskazują stronę całej kategorii; jako największe dostają tylko produkty
spoza mniejszych podkategorii. Nowości, Bestsellery, Promocje i Polecane są pominięte,
bo to filtry na produktach z innych kategorii.
"""

BASE_URL = "https://dobrakaloria.pl"

# Gdy robots.txt nie wskazuje sitemap produktów (sitemap.load_sitemap_urls)
SITEMAP_FALLBACK = [
    "https://dobrakaloria.pl/sitemap-products.xml",
    "https://dobrakaloria.pl/sitemap-categories.xml",
    "https://dobrakaloria.pl/sitemap.xml",
]

# Pełna lista produktów, tylko do kontroli kompletności (main.find_missing)
ALL_PRODUCTS_URL = "https://dobrakaloria.pl/2-wszystkie-produkty"

# Produkty spoza wszystkich podkategorii źródła: id -> [kategoria, podkategoria]
MANUAL_CATEGORIES = {
    134: ["Zestawy słodyczy", "Pozostałe zestawy słodyczy"],  # Zestaw jabłko & cynamon 20szt
}

CATEGORY_TREE = {
    "Batony": {
        "Daktyle w posypce": "https://dobrakaloria.pl/106-daktyle-w-posypce",
        "Batony daktylowe": "https://dobrakaloria.pl/31-batony-daktylowe",
        "Batony klasyczne": "https://dobrakaloria.pl/32-batony-klasyczne",
        "Batony z dodatkiem kokosa": "https://dobrakaloria.pl/36-batony-z-dodatkiem-kokosa",
        "Batony z orzechami": "https://dobrakaloria.pl/37-batony-z-orzechami",
        "Batony z dodatkiem czekolady": "https://dobrakaloria.pl/42-batony-z-dodatkiem-czekolady",
        "Batony proteinowe": "https://dobrakaloria.pl/46-batony-proteinowe",
        "Batony z nerkowców": "https://dobrakaloria.pl/40-batony-o-smaku-ciast",
        "Pozostałe batony": "https://dobrakaloria.pl/102-wszystkie-batony",
    },
    "Mini batoniki": {
        "Mini batoniki - 6 sztuk": "https://dobrakaloria.pl/39-mini-batoniki-6-sztuk",
        "O smaku ciast": "https://dobrakaloria.pl/41-o-smaku-ciast",
        "O smaku deserów": "https://dobrakaloria.pl/43-o-smaku-deserow",
        "O smaku kultowych batonów": "https://dobrakaloria.pl/44-o-kultowych-smakach",
        "Klasyczne smaki": "https://dobrakaloria.pl/45-klasyczne-smaki",
        "Do zadań specjalnych": "https://dobrakaloria.pl/95-do-zadan-specjalnych",
        "Proteinowe z niskim IG": "https://dobrakaloria.pl/100-batony-proteinowe-z-niskiem-ig",
        "Pozostałe mini batoniki": "https://dobrakaloria.pl/103-wszystkie-mini-batoniki",
    },
    "Kulki": {
        "Kulki RAW z kakao": "https://dobrakaloria.pl/49-czekoladowo-daktylowe",
        "Kulki zbożowe": "https://dobrakaloria.pl/50-owsiane",
        "Kulki w pudrze owocowym": "https://dobrakaloria.pl/104-kulki-w-pudrze-owocowym",
        "Pozostałe kulki": "https://dobrakaloria.pl/48-kulki",
    },
    "Zdrowe śniadanie": {
        "Produkty śniadaniowe": "https://dobrakaloria.pl/58-produkty-sniadaniowe",
        "Przekąski śniadaniowe": "https://dobrakaloria.pl/59-przekaski-sniadaniowe",
        "Kremy orzechowe": "https://dobrakaloria.pl/105-kremy-orzechowe",
        "Pozostałe śniadaniowe": "https://dobrakaloria.pl/55-zdrowe-sniadanie",
    },
    "Zamienniki mięsa": {
        "Szybkie obiady": "https://dobrakaloria.pl/68-szybkie-obiady",
        "Pasztety": "https://dobrakaloria.pl/70-pasztety",
        "Burgery": "https://dobrakaloria.pl/96-burgery",
        "Kiełbaski, parówki i kaszanki": "https://dobrakaloria.pl/69-kielbaski-i-kaszanki",
        "Zdrowy grill": "https://dobrakaloria.pl/57-zdrowy-grill",
        "Promocje z krótką datą": "https://dobrakaloria.pl/97-promocje-z-krotka-data",
        "Pozostałe zamienniki mięsa": "https://dobrakaloria.pl/56-zamienniki-miesa",
    },
    "Zestawy słodyczy": {
        "W zestawie taniej": "https://dobrakaloria.pl/86-w-zestawie-taniej",
        "Na prezent": "https://dobrakaloria.pl/87-na-prezent",
        "Pozostałe zestawy słodyczy": "https://dobrakaloria.pl/85-zestawy-slodyczy",
    },
    "Zestawy niemięs": {
        "Duży": "https://dobrakaloria.pl/89-duzy",
        "Średni": "https://dobrakaloria.pl/90-sredni",
        "Grill": "https://dobrakaloria.pl/91-grill",
        "Na próbę": "https://dobrakaloria.pl/92-na-probe",
        "Pozostałe zestawy niemięs": "https://dobrakaloria.pl/88-zestawy-niemies",
    },
}
