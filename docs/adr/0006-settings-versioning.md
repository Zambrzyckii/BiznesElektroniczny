# ADR 0006: Wersjonowanie ustawień sklepu

- **Status:** zaakceptowana
- **Data:** 2026-11-17

## Kontekst

- Numer `ADR 0006` wynika z faktu, że numery 0004 i 0005 zajmują otwarte PR-y #51 i #52 (ta sama zasada co w `docs/adr/0002-repository-workflow.md:12`).
- Wymaganie W3 [K] mówi, że sklep startuje z czystego klona jedną komendą. Issue wymienia też D4 i D6, które cytujemy tylko jako kody, bo ich znaczenia nie ma w repozytorium.
- Ustawienia wyklikane w panelu leżą w bazie w wolumenie `db-data` (`deploy/compose.yaml:10`). Czysty klon dostaje świeżą instalację, więc ustawienia spoza repozytorium znikają.
- Ustawienia dzielą się na obszary. #31 obejmuje język, lokalizację, walutę i podatki. #34 obejmuje płatności i faktury przy płatności za pobraniem. #35 obejmuje przewoźników z darmową dostawą i limitem wagi. #36 obejmuje górne menu, stopkę, wyszukiwarkę i informację o cookies. Strony CMS i poczta nie mają przypisanego issue.
- Fakty o PrestaShop 8.2.8, które wymuszają decyzję.
  - Tabela `ps_configuration` ma klucz główny `id_configuration`, a kolumna `name` nie jest unikalna (`db_structure.sql`).
  - Kolumna `ps_module.name` jest unikalna. Instalacja modułu uruchamia jego kod, który tworzy tabele, haki i czasem statusy zamówień.
  - Każdy zapis przewoźnika w panelu tworzy nowy `id_carrier` i oznacza stary jako `deleted` (`AdminCarrierWizardController::ajaxProcessFinishStep`).
  - Edycja używanego podatku tworzy nowy `id_tax`, historyzuje stary i wywołuje `TaxRule::swapTaxId` (`Tax::update`).
  - Identyfikatory łączą obszary. Przewoźnicy wskazują grupy reguł podatkowych (`ps_carrier_tax_rules_group_shop.id_tax_rules_group`) i strefy (`ps_carrier_zone`, `ps_delivery`). Kraje wskazują strefy i waluty (`ps_country.id_zone`, `id_currency`). Produkty wskazują grupy reguł podatkowych (`ps_product.id_tax_rules_group`).
  - Instalator kopiuje `ADMIN_MAIL` do `PS_SHOP_EMAIL`, do `PS_LOGS_EMAIL_RECEIVERS` i do `ps_contact.email` każdego kontaktu (`Install::configureShop`).
  - Login i hasło SMTP to klucze `PS_MAIL_USER` i `PS_MAIL_PASSWD` (`Mail::send`).
  - Logo, obrazy modułów i pliki motywu to pliki w `shop-data` (`deploy/compose.yaml:38`), a nie wiersze w bazie.
- Poza zakresem tej decyzji są kod eksportu i odtwarzania (#16), import danych (#17), własny obraz sklepu (#12) i Mailpit (#14).

## Rozważane opcje

| Opcja | Zalety | Wady |
|---|---|---|
| **Migawka SQL tabel z identyfikatorami i `bin/console` dla kluczy, modułów i motywu (wybrana)** | Obejmuje każdy obszar. Identyfikatory są spójne, bo pochodzą z jednej bazy. Klucze i moduły wracają po nazwie. Nie ma w niej sekretów. | Dwa narzędzia. Każdy eksport musi pochodzić ze stosu odbudowanego z `main`. |
| Pełny zrzut bazy | Jedna komenda. | Zawiera `ps_customer`, `ps_employee.passwd`, `ps_webservice_account.key` i e-mail administratora, a jego diffy są nieczytelne. |
| Eksport wybranych tabel SQL w całości, w tym `ps_configuration` i `ps_module` | Jedno narzędzie (`mariadb-dump`). | Pełna `ps_configuration` zawiera `PS_MAIL_PASSWD` i `ADMIN_MAIL`. Wiersze odtworzone po `id` trafiają na złe klucze. Wiersz w `ps_module` nie instaluje modułu. |
| Skrypty przez Webservice API | Czytelne zmiany w PR-ach. Istnieją zasoby `carriers`, `taxes`, `tax_rule_groups`, `countries`, `zones`, `currencies`, `content_management_system` i `configurations`. | Wymaga klucza w `.env`. Nie ma zasobu dla modułów, haków ani motywu. Wymaga najwięcej kodu. |
| Tylko `bin/console` | Wszystko po nazwie, przez `prestashop:config` (get, set, remove), `prestashop:module` (install, enable, disable i inne) oraz `prestashop:theme:enable`. | Brak poleceń dla podatków, przewoźników, CMS i menu. |

## Decyzja

Wybieramy migawkę SQL tabel z identyfikatorami oraz `bin/console` dla kluczy, modułów i motywu.

| Mechanizm | Co obejmuje |
|---|---|
| Migawka SQL | Wszystkie tabele z identyfikatorami z "Listy ustawień" (lokalizacja, przewoźnicy, CMS, menu, stopka, aliasy wyszukiwarki). Eksport to jedno uruchomienie `mariadb-dump` dla całej grupy z jednej bazy, jeden wiersz w linii (`--skip-extended-insert`, `--order-by-primary`, `--skip-dump-date`). Odtworzenie opróżnia każdą tabelę i wypełnia ją z migawki, więc wiersze instalatora są zastępowane, a nigdy łączone. Identyfikatory są spójne, bo każdy wiersz i każdy klucz pochodzi z tej samej bazy w tej samej chwili. |
| Klucze po nazwie | Lista dozwolonych nazw odtwarzana przez `prestashop:config set`. Wartości per język (`--lang`) są w niej uwzględnione, na przykład `PS_INVOICE_FREE_TEXT`. Klucze z identyfikatorami, takie jak `PS_CURRENCY_DEFAULT`, `PS_COUNTRY_DEFAULT`, `PS_CARRIER_DEFAULT` i `PS_CONDITIONS_CMS_ID`, są eksportowane razem z migawką. |
| Moduły po nazwie | Lista modułów z oczekiwanym stanem, odtwarzana przez `prestashop:module install`, `enable` i `disable`. Pozycje w hakach i ograniczenia płatności są zapisane przez nazwę modułu i nazwę haka. |
| Motyw | `prestashop:theme:enable`. |
| Pliki | Logo, obrazy modułów i motyw trafiają do `shop/` (#12). |

### Kolejność przywracania

1. Zainstaluj sklep (ADR 0003).
2. Włącz motyw.
3. Zainstaluj i włącz moduły.
4. Odtwórz migawkę SQL.
5. Odtwórz klucze po nazwie.
6. Odtwórz pozycje modułów i ograniczenia płatności.
7. Zaimportuj produkty (#17).

Moduły idą przed migawką, bo tworzą tabele, które migawka wypełnia. Ograniczenia idą po niej, bo `ps_module_carrier` używa `id_reference` przewoźników, a `ps_module_country` i `ps_module_currency` używają identyfikatorów z migawki.

### Zasady zespołu

- Wersjonujemy tylko to, co nazywa "Lista ustawień", bo jest to lista dozwolonych pozycji.
- Nowy klucz lub nowa tabela trafia na listę w tym samym PR, po sprawdzeniu, że nie zawiera danych osobowych ani sekretu.
- Żadna wartość z `deploy/.env` nie trafia do eksportu.
- Migawkę eksportujemy w całości, nigdy jednym obszarem naraz.
- Przed konfigurowaniem i przed eksportem odbudowujemy stos z aktualnego `main`.
- Kolejność scalania to #31 przed #34 i #35.
- Jeśli diff pokazuje zmienioną tabelę spoza własnego obszaru, eksportujemy ponownie ze stosu odtworzonego z `main`. Recenzent to sprawdza.

### Jak zapisujemy zmiany ustawień

Dotyczy zadań #31, #34, #35 i #36.

1. Konfigurujesz sklep na świeżym stosie z aktualnego `main`.
2. Zapisujesz każde kliknięcie w roboczym (draft) PR-ze, razem ze ścieżką w panelu, wartością i nazwą klucza, jeśli ją znasz.
3. Po scaleniu #16 odtwarzasz `main`, powtarzasz kliknięcia według swoich notatek, eksportujesz, sprawdzasz diff i dodajesz nowe klucze do listy.
4. Oznaczasz PR jako gotowy do recenzji (Ready for review) tylko z plikami eksportu. Recenzent sprawdza ustawienie na czystym stosie.

## Lista ustawień

| Obszar | Tabele lub klucze | Kto wypełnia na starcie | Dane osobowe |
|---|---|---|---|
| Lokalizacja (#31) | Tabele migawki `ps_currency`, `ps_currency_lang`, `ps_currency_shop`, `ps_tax`, `ps_tax_lang`, `ps_tax_rules_group`, `ps_tax_rules_group_shop`, `ps_tax_rule`, `ps_country`, `ps_country_lang`, `ps_country_shop`, `ps_zone`, `ps_zone_shop`, `ps_state`. Klucze `PS_CURRENCY_DEFAULT`, `PS_COUNTRY_DEFAULT`, `PS_LOCALE_LANGUAGE`, `PS_LOCALE_COUNTRY`, `PS_TIMEZONE`, `PS_TAX`, `PS_TAX_DISPLAY`, `PS_TAX_ADDRESS_TYPE`, `PS_WEIGHT_UNIT`. | Paczka `pl.xml` daje walutę PLN, podatki PTU PL 23%, 8%, 5% i 0, grupy "PL Standard Rate (23%)", "PL Reduced Rate (8%)", "PL Reduced Rate (5%)", "PL Exempted Rate (0%)" i "EU VAT For Virtual Products" oraz jednostki kg, L, cm, m i km. Instalator ustawia `PS_LANG_DEFAULT`, `PS_COUNTRY_DEFAULT`, `PS_LOCALE_*` i `PS_TIMEZONE`. | Brak. |
| Przewoźnicy (#35) | Tabele migawki `ps_carrier` (w tym `max_weight`), `ps_carrier_lang`, `ps_carrier_zone`, `ps_carrier_group`, `ps_carrier_shop`, `ps_carrier_tax_rules_group_shop`, `ps_range_weight`, `ps_range_price`, `ps_delivery`. Klucze `PS_CARRIER_DEFAULT`, `PS_SHIPPING_FREE_PRICE`, `PS_SHIPPING_FREE_WEIGHT`, `PS_SHIPPING_HANDLING`, `PS_SHIPPING_METHOD`. | Instalator. | Brak. |
| Płatności i faktury (#34) | Moduł `ps_cashondelivery`, który jest w obrazie (`composer.json`, ^2.0). Ograniczenia `ps_module_carrier`, `ps_module_country` i `ps_module_currency` zapisane przez nazwę modułu. Klucze faktur `PS_INVOICE`, `PS_INVOICE_TAXES_BREAKDOWN`, `PS_PDF_IMG_INVOICE`, `PS_INVOICE_PREFIX`, `PS_INVOICE_USE_YEAR`, `PS_INVOICE_RESET`, `PS_INVOICE_YEAR_POS`, `PS_INVOICE_START_NUMBER`, `PS_INVOICE_LEGAL_FREE_TEXT`, `PS_INVOICE_FREE_TEXT`, `PS_INVOICE_MODEL`, `PS_PDF_USE_CACHE` oraz `PS_DELIVERY_PREFIX`. Statusy zamówień. Tabela `ps_order_state` domyślnie nie jest wersjonowana. Moduł odtwarza swój status przy instalacji i zapisuje jego id w `PS_OS_COD_VALIDATION` (sprawdzone w v2.0.1). Jeśli #34 musi edytować status, do migawki dochodzą `ps_order_state` i `ps_order_state_lang`, do listy wszystkie klucze `PS_OS_*`, a pliki ikon statusów do `shop/`. | Instalator i moduł. | Brak. |
| Menu, stopka, wyszukiwarka (#36) | Moduł `ps_mainmenu` z tabelami `ps_linksmenutop` i `ps_linksmenutop_lang` oraz kluczem `MOD_BLOCKTOPMENU_ITEMS` (sprawdzone na master 2.3.6). Moduł `ps_linklist` z tabelami `ps_link_block`, `ps_link_block_lang` i `ps_link_block_shop` (sprawdzone w v6.0.7), gdzie `content` zawiera JSON z polami `cms`, `product`, `static` i `category`. Moduł `ps_searchbar` nie ma własnych tabel ani kluczy (master 2.1.4). Klucze wyszukiwania `PS_SEARCH_MINWORDLEN`, `PS_SEARCH_BLACKLIST`, `PS_SEARCH_AJAX`, `PS_SEARCH_INDEXATION`, `PS_SEARCH_FUZZY`, `PS_SEARCH_FUZZY_MAX_LOOP`, `PS_SEARCH_MAX_WORD_LENGTH` i klucze `PS_SEARCH_WEIGHT_*`. Aliasy wyszukiwania w `ps_alias`. Informacja o cookies. Żaden moduł w obrazie nie ma "cookie" w nazwie (`composer.json` 8.2.8), a `psgdpr` nie pokazuje banera (master), więc rozwiązanie wybiera #36. Moduł spoza obrazu trafia do `shop/`, a jego tabele przechodzą przez regułę sprawdzenia. | Instalator i moduły. | Brak, poza modułem cookies, którego jeszcze nie znamy. |
| Strony CMS | Tabele migawki `ps_cms`, `ps_cms_lang`, `ps_cms_shop`, `ps_cms_category`, `ps_cms_category_lang`, `ps_cms_category_shop`, `ps_cms_role` oraz klucz `PS_CONDITIONS_CMS_ID`. | Instalator. | Brak. |
| Moduły | Nazwy i stany oraz pozycje w hakach według nazwy. Własne tabele modułu trafiają na listę dopiero po sprawdzeniu. | Instalator. | Brak. |
| Motyw | `ps_shop.theme_name` przez `theme:enable`. Pliki trafiają do `shop/`. | Instalator. | Brak. |
| Poczta | `PS_MAIL_METHOD`, `PS_MAIL_SERVER`, `PS_MAIL_SMTP_PORT`, `PS_MAIL_SMTP_ENCRYPTION`, `PS_MAIL_TYPE`, `PS_LOG_EMAILS` oraz `PS_SHOP_EMAIL` tylko z wymyślonym adresem. | Instalator. | Brak. |

Założenie, którego nie sprawdziliśmy w kodzie. `Install.php` nie ustawia `PS_CURRENCY_DEFAULT`, jego domyślna wartość w `configuration.xml` to 1, a to czy id 1 jest walutą PLN sprawdza #31. Źródło krajów i stref też nie jest sprawdzone.

Tabela `ps_lang` nie jest wersjonowana i zostaje taka, jaką instalator tworzy z `PS_LANGUAGE=pl` (`deploy/compose.yaml:29`). Dodanie języka pobiera pliki (`Language::downloadAndInstallLanguagePack`), co leży poza tym ADR.

### Dane wykluczone

| Tabela lub klucz | Co zawiera |
|---|---|
| `ps_customer` | `email`, `passwd`, `reset_password_token`. |
| `ps_employee` | `email`, `passwd`, `reset_password_token`. Konto administratora powstaje z `deploy/.env`. |
| `ps_webservice_account` | `key`. |
| `ps_customer_session` i `ps_employee_session` | Tokeny. |
| `ps_guest` i `ps_connections` | `ip_address`. |
| `ps_mail` | `recipient`. |
| `ps_log` | `id_employee`. |
| `ps_contact` | `email` równy `ADMIN_MAIL`. |
| `ps_order_invoice` | Dane zamówienia (`id_order`, `number`, kwoty, `shop_address`). |
| `ps_emailsubscription` | `email`, `ip_registration_newsletter` (tabela modułu, sprawdzone na master 3.0.1). |
| Tabela logu `psgdpr` (plik `psgdpr_log.sql` na master) | Id i imię klienta. Nazwa tabeli `ps_psgdpr_log` to założenie. |
| `ps_search_index` i `ps_search_word` | Indeks, który sklep odbudowuje sam. |
| `ps_shop_url`, `PS_SHOP_DOMAIN`, `PS_SHOP_DOMAIN_SSL` | Domena z `PS_DOMAIN` (`deploy/compose.yaml:31`). |
| `PS_MAIL_USER` i `PS_MAIL_PASSWD` | Dane logowania SMTP. |
| `PS_SHOP_EMAIL` z wartością instalatora oraz `PS_LOGS_EMAIL_RECEIVERS` | `ADMIN_MAIL`. |
| `app/config/parameters.php` | Sekrety. Plik jest już ignorowany (`.gitignore:8`). |

Zamówienia, koszyki i adresy też są wykluczone, bo lista jest listą dozwolonych pozycji.

## Konsekwencje

- Eksport nie zawiera sekretów, jego diffy są czytelne, a jedna migawka pochłania dryf identyfikatorów.
- Po edycji przewoźnika albo używanego podatku w diffie pojawiają się nowe wiersze.
- Równoległe PR-y są ryzykiem. Git nie pokaże konfliktu, gdy eksport #35 wskazuje grupy podatkowe sprzed #31. Dlatego istnieje kolejność scalania i ponowny eksport.
- Identyfikatory, na które migawka wskazuje, ale których nie zawiera, zostają takie, jakie tworzy instalator. Ich stabilność to założenie. `ps_carrier_group` wskazuje `ps_group`. `link_block.id_hook` wskazuje `ps_hook`. Tabele `_lang` wskazują `ps_lang`. Tabele `_shop` wskazują sklep 1. Najsłabszym punktem są haki rejestrowane przez moduły.
- Wiersze tworzone później wskazują na migawkę. Import (#17) zapisuje `ps_product.id_tax_rules_group`. `link_block.content` zawiera identyfikatory kategorii i produktów. `MOD_BLOCKTOPMENU_ITEMS` prawdopodobnie zawiera identyfikatory kategorii, a ten format to założenie. Dlatego odtwarzanie działa przed #17, a #17 musi znajdować grupy podatkowe po nazwie i dawać te same identyfikatory kategorii w każdym czystym uruchomieniu.
- To, czy `bin/console` istnieje w obrazie i czy `theme:enable` resetuje haki modułów, to założenia, które sprawdza #16.
- Pliki w `shop-data` nie są odświeżane z obrazu (`docs/adr/0003-container-architecture.md:69`).

## Źródła

Każde źródło sprawdzono na tagu 8.2.8, chyba że zaznaczono "gałąź 8.2.x" albo wersję modułu.

- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/install-dev/data/db_structure.sql
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/install-dev/data/xml/configuration.xml
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/src/PrestaShopBundle/Install/Install.php (`configureShop`, `installDefaultData`)
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/localization/pl.xml
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/classes/tax/Tax.php (`update`, `historize`)
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/controllers/admin/AdminCarrierWizardController.php (`ajaxProcessFinishStep`)
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/src/Adapter/Invoice/InvoiceOptionsConfiguration.php
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/classes/Language.php
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/composer.json
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/src/PrestaShopBundle/Command/ConfigCommand.php
- gałąź 8.2.x: https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.x/src/PrestaShopBundle/Command/ModuleCommand.php
- gałąź 8.2.x: https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.x/src/PrestaShopBundle/Command/ThemeEnablerCommand.php
- gałąź 8.2.x: https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.x/classes/webservice/WebserviceRequest.php (`getResources`)
- gałąź 8.2.x: https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.x/classes/Mail.php
- gałąź 8.2.x: https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.x/classes/shop/Shop.php
- https://raw.githubusercontent.com/PrestaShop/ps_linklist/v6.0.7/src/Repository/LinkBlockRepository.php
- https://raw.githubusercontent.com/PrestaShop/ps_cashondelivery/v2.0.1/ps_cashondelivery.php
- https://raw.githubusercontent.com/PrestaShop/ps_mainmenu/master/ps_mainmenu.php
- https://raw.githubusercontent.com/PrestaShop/ps_searchbar/master/ps_searchbar.php
- https://raw.githubusercontent.com/PrestaShop/ps_emailsubscription/master/ps_emailsubscription.php
- https://github.com/PrestaShop/psgdpr/tree/master/sql/install
- https://mariadb.com/kb/en/mariadb-dump/
