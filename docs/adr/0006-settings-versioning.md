# ADR 0006: Wersjonowanie ustawień sklepu

- **Status:** zaakceptowana
- **Data:** 2026-11-17

## Kontekst

- Numer `ADR 0006` to kolejny wolny numer po ADR 0004 i 0005, które są już na `main` (ta sama zasada co w `docs/adr/0002-repository-workflow.md:12`).
- Wymaganie W3 [K] mówi, że sklep startuje z czystego klona jedną komendą. Issue wymienia też D4 i D6, które cytujemy tylko jako kody, bo ich znaczenia nie ma w repozytorium.
- Ustawienia wyklikane w panelu leżą w bazie w wolumenie `db-data` (`deploy/compose.yaml:10`). Czysty klon dostaje świeżą instalację, więc ustawienia spoza repozytorium znikają.
- Ustawienia dzielą się na obszary. #31 obejmuje język, lokalizację, walutę i podatki. #34 obejmuje płatności i faktury przy płatności za pobraniem. #35 obejmuje przewoźników z darmową dostawą i limitem wagi. #36 obejmuje górne menu, stopkę, wyszukiwarkę i informację o cookies. #32 i #33 obejmują strony CMS, a #14 pocztę.
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
| **Migawka SQL tabel z identyfikatorami i `bin/console` dla kluczy, modułów i motywu (wybrana)** | Obejmuje każdy obszar. Identyfikatory są spójne, bo pochodzą z jednej bazy. Klucze i moduły wracają po nazwie. Nie ma w niej sekretów. | Dwa narzędzia i własny skrypt SQL. Każdy eksport musi pochodzić ze stosu odbudowanego z `main`. |
| Pełny zrzut bazy | Jedna komenda. | Zawiera `ps_customer`, `ps_employee.passwd`, `ps_webservice_account.key` i e-mail administratora, a jego diffy są nieczytelne. |
| Eksport wybranych tabel SQL w całości, w tym `ps_configuration` i `ps_module` | Jedno narzędzie (`mariadb-dump`). | Pełna `ps_configuration` zawiera `PS_MAIL_PASSWD` i `ADMIN_MAIL`. Wiersze odtworzone po `id` trafiają na złe klucze. Wiersz w `ps_module` nie instaluje modułu. |
| Skrypty przez Webservice API | Czytelne zmiany w PR-ach. Istnieją zasoby `carriers`, `taxes`, `tax_rule_groups`, `countries`, `zones`, `currencies`, `content_management_system` i `configurations`. | Wymaga klucza w `.env`. Nie ma zasobu dla modułów, haków ani motywu. Wymaga najwięcej kodu. |
| Tylko `bin/console` | Wszystko po nazwie, przez `prestashop:config` (get, set, remove), `prestashop:module` (install, enable, disable i inne) oraz `prestashop:theme:enable`. | Brak poleceń dla podatków, przewoźników, CMS i menu. |

## Decyzja

Wybieramy migawkę SQL tabel z identyfikatorami oraz `bin/console` dla kluczy, modułów i motywu.

| Mechanizm | Co obejmuje |
|---|---|
| Migawka SQL | Wszystkie tabele z identyfikatorami z "Listy ustawień" (lokalizacja, przewoźnicy, CMS, menu, stopka, aliasy wyszukiwarki). Eksport to jedno uruchomienie `mariadb-dump` dla całej grupy z jednej bazy, jeden wiersz w linii (`--skip-extended-insert`, `--order-by-primary`, `--skip-dump-date`). Odtworzenie opróżnia każdą tabelę i wypełnia ją z migawki, więc wiersze instalatora są zastępowane, a nigdy łączone. Identyfikatory są spójne, bo każdy wiersz i każdy klucz pochodzi z tej samej bazy w tej samej chwili. Razem z migawką eksportujemy pliki logo przewoźników `img/s/<id_carrier>.jpg`, bo ich nazwy są identyfikatorami z migawki. Leżą w repozytorium obok plików migawki, a dokładny katalog ustala #16. |
| Klucze po nazwie | Lista dozwolonych nazw odtwarzana przez `prestashop:config set`. Wartości per język (`--lang`) są w niej uwzględnione, na przykład `PS_INVOICE_FREE_TEXT`. Klucze z identyfikatorami, takie jak `PS_CURRENCY_DEFAULT`, `PS_COUNTRY_DEFAULT`, `PS_CARRIER_DEFAULT` i `PS_CONDITIONS_CMS_ID`, są eksportowane razem z migawką. |
| Skrypt startowy | Klucze, które mają tę samą wartość na każdym stosie i których nie zmieniamy w panelu, na przykład serwer poczty z compose (#14) albo strefa czasowa i wykrywanie kraju (#31). Skrypt w `deploy/init-scripts/` ustawia je przez `prestashop:config set` przy każdym starcie kontenera sklepu, a compose montuje go do `/tmp/init-scripts/`. Ten katalog i montowanie jeszcze nie są na `main`. Wnoszą je PR-y #54 (#14) i #61 (#31). Zmiana w panelu wraca więc po restarcie do wartości ze skryptu, dlatego te klucze nie trafiają do eksportu. Skrypty z kluczami leżą w `deploy/` obok zmiennych instalacji, a nie w katalogu `shop/init-scripts/`, który według ADR 0008 z PR-a #55 (#12) trafia do obrazu sklepu. Klaster w etapie 2 nie ma repozytorium, więc te pliki, podobnie jak pliki proxy z #13, trzeba tam dostarczyć inaczej, na przykład jako `configs` albo w obrazie. |
| Moduły po nazwie | Lista modułów z oczekiwanym stanem, odtwarzana przez `prestashop:module install`, `enable` i `disable`. Pozycje w hakach i ograniczenia płatności odtwarza #16 własnym skryptem SQL, który dopasowuje wiersze po `ps_module.name` i `ps_hook.name`, a przewoźników po `id_reference`. |
| Motyw | `prestashop:theme:enable`. |
| Pliki | Logo, favicon, obrazy modułów i motyw trafiają do `shop/` (#12). Logo przewoźników idą razem z migawką. |

### Kolejność przywracania

1. Zainstaluj sklep (ADR 0003).
2. Włącz motyw.
3. Zainstaluj i włącz moduły.
4. Odtwórz migawkę SQL i pliki logo przewoźników `img/s/`.
5. Odtwórz klucze po nazwie.
6. Odtwórz pozycje modułów i ograniczenia płatności skryptem SQL.
7. Zaimportuj produkty (#17).

Moduły idą przed migawką, bo tworzą tabele, które migawka wypełnia. Ograniczenia idą po niej, bo `ps_module_carrier` używa `id_reference` przewoźników, a `ps_module_country` i `ps_module_currency` używają identyfikatorów z migawki.

### Zasady zespołu

- Wersjonujemy tylko to, co nazywa "Lista ustawień", bo jest to lista dozwolonych pozycji.
- Nowy klucz lub nowa tabela trafia na listę w tym samym PR, po sprawdzeniu, że nie zawiera danych osobowych ani sekretu.
- Żadna wartość z `deploy/.env` nie trafia do eksportu.
- Migawkę eksportujemy w całości, nigdy jednym obszarem naraz.
- Przed konfigurowaniem i przed eksportem odbudowujemy stos z aktualnego `main`.
- Kolejność scalania to #31 przed #34 i #35, a #34 i #35 przed #32 i #33, bo strony CMS opisują płatności i przewoźników.
- Jeśli diff pokazuje zmienioną tabelę spoza własnego obszaru, eksportujemy ponownie ze stosu odtworzonego z `main`. Recenzent to sprawdza.

### Jak zapisujemy zmiany ustawień

Dotyczy zadań #34, #35 i #36. #31 ich nie potrzebuje, bo zmienia tylko instalację w `deploy/compose.yaml` i skrypt startowy.

1. Konfigurujesz sklep na świeżym stosie z aktualnego `main`.
2. Zapisujesz każde kliknięcie w roboczym (draft) PR-ze, razem ze ścieżką w panelu, wartością i nazwą klucza, jeśli ją znasz.
3. Po scaleniu #16 odtwarzasz `main`, powtarzasz kliknięcia według swoich notatek, eksportujesz, sprawdzasz diff i dodajesz nowe klucze do listy.
4. Oznaczasz PR jako gotowy do recenzji (Ready for review) tylko z plikami eksportu. Recenzent sprawdza ustawienie na czystym stosie.

Strony CMS z #32 i #33 przechodzą przez te same kroki. Ich teksty do wklejenia w kroku 3 leżą do tego czasu w `shop/cms/` jako pliki tymczasowe, które krok 4 usuwa z PR-a.

## Lista ustawień

| Obszar | Tabele lub klucze | Kto wypełnia na starcie | Dane osobowe i sekrety |
|---|---|---|---|
| Lokalizacja (#31) | Tabele migawki `ps_currency`, `ps_currency_lang`, `ps_currency_shop`, `ps_tax`, `ps_tax_lang`, `ps_tax_rules_group`, `ps_tax_rules_group_shop`, `ps_tax_rule`, `ps_country`, `ps_country_lang`, `ps_country_shop`, `ps_zone`, `ps_zone_shop`, `ps_state`. Klucze `PS_CURRENCY_DEFAULT`, `PS_COUNTRY_DEFAULT`, `PS_LOCALE_LANGUAGE`, `PS_LOCALE_COUNTRY`, `PS_TAX`, `PS_TAX_DISPLAY`, `PS_TAX_ADDRESS_TYPE`, `PS_WEIGHT_UNIT`. Klucze `PS_DETECT_COUNTRY` i `PS_TIMEZONE` ustawia skrypt startowy `deploy/init-scripts/configure-locale.sh`. | Paczka `pl.xml`, którą instalator wczytuje dzięki `PS_COUNTRY=pl` (`deploy/compose.yaml`), daje domyślną walutę PLN, jedyny język `pl`, podatki PTU PL 23%, 8%, 5% i 0, grupy "PL Standard Rate (23%)", "PL Reduced Rate (8%)", "PL Reduced Rate (5%)", "PL Exempted Rate (0%)" i "EU VAT For Virtual Products" oraz jednostki kg, L, cm, m i km. Instalator ustawia `PS_LANG_DEFAULT`, `PS_COUNTRY_DEFAULT`, `PS_LOCALE_*`, `PS_DETECT_COUNTRY` równe 1 i `PS_TIMEZONE` równe `Europe/Paris` (`datas.php`, sprawdzone na działającym stosie). Skrypt startowy zmienia je na 0 i `Europe/Warsaw`. Grupy klientów pokazują ceny brutto (`price_display_method` równe 0 w `group.xml`). | Brak danych osobowych i sekretów. |
| Przewoźnicy (#35) | Tabele migawki `ps_carrier` (w tym `max_weight`), `ps_carrier_lang`, `ps_carrier_zone`, `ps_carrier_group`, `ps_carrier_shop`, `ps_carrier_tax_rules_group_shop`, `ps_range_weight`, `ps_range_price`, `ps_delivery`. Klucze `PS_CARRIER_DEFAULT`, `PS_SHIPPING_FREE_PRICE`, `PS_SHIPPING_FREE_WEIGHT`, `PS_SHIPPING_HANDLING`, `PS_SHIPPING_METHOD`. | Instalator. | Brak danych osobowych i sekretów. |
| Płatności i faktury (#34) | Moduł `ps_cashondelivery`, który jest w obrazie (`composer.json`, ^2.0). Moduł przelewu `ps_wirepayment` (^2.1, sprawdzone w v2.2.0 z `composer.lock`) z kluczami `BANK_WIRE_OWNER`, `BANK_WIRE_DETAILS`, `BANK_WIRE_ADDRESS`, `BANK_WIRE_RESERVATION_DAYS`, `BANK_WIRE_CUSTOM_TEXT` (wartość per język) i `BANK_WIRE_PAYMENT_INVITE`. Stan modułu `ps_checkpayment` (^2), który też jest w obrazie, zapisujemy na liście modułów. Ograniczenia `ps_module_carrier`, `ps_module_country` i `ps_module_currency` zapisane przez nazwę modułu. Klucze faktur `PS_INVOICE`, `PS_INVOICE_TAXES_BREAKDOWN`, `PS_PDF_IMG_INVOICE`, `PS_INVOICE_PREFIX`, `PS_INVOICE_USE_YEAR`, `PS_INVOICE_RESET`, `PS_INVOICE_YEAR_POS`, `PS_INVOICE_START_NUMBER`, `PS_INVOICE_LEGAL_FREE_TEXT`, `PS_INVOICE_FREE_TEXT`, `PS_INVOICE_MODEL`, `PS_PDF_USE_CACHE` oraz `PS_DELIVERY_PREFIX`. Statusy zamówień. Tabela `ps_order_state` domyślnie nie jest wersjonowana. Moduł odtwarza swój status przy instalacji i zapisuje jego id w `PS_OS_COD_VALIDATION` (sprawdzone w v2.0.1). Jeśli #34 musi edytować status, do migawki dochodzą `ps_order_state` i `ps_order_state_lang`, do listy wszystkie klucze `PS_OS_*`, a pliki ikon statusów do `shop/`. | Instalator i moduł. | Brak danych osobowych i sekretów. |
| Menu, stopka, wyszukiwarka (#36) | Moduł `ps_mainmenu` z tabelami `ps_linksmenutop` i `ps_linksmenutop_lang` oraz kluczem `MOD_BLOCKTOPMENU_ITEMS` (sprawdzone na master 2.3.6). Moduł `ps_linklist` z tabelami `ps_link_block`, `ps_link_block_lang` i `ps_link_block_shop` (sprawdzone w v6.0.7), gdzie `content` zawiera JSON z polami `cms`, `product`, `static` i `category`. Moduł `ps_searchbar` nie ma własnych tabel ani kluczy (master 2.1.4). Klucze wyszukiwania `PS_SEARCH_MINWORDLEN`, `PS_SEARCH_BLACKLIST`, `PS_SEARCH_AJAX`, `PS_SEARCH_INDEXATION`, `PS_SEARCH_FUZZY`, `PS_SEARCH_FUZZY_MAX_LOOP`, `PS_SEARCH_MAX_WORD_LENGTH` i klucze `PS_SEARCH_WEIGHT_*`. Aliasy wyszukiwania w `ps_alias`. Informacja o cookies. Żaden moduł w obrazie nie ma "cookie" w nazwie (`composer.json` 8.2.8), a `psgdpr` nie pokazuje banera (master), więc rozwiązanie wybiera #36. Moduł spoza obrazu trafia do `shop/`, a jego tabele przechodzą przez regułę sprawdzenia. | Instalator i moduły. | Brak w wymienionych pozycjach. Moduł cookies i jego tabele trafiają na listę dopiero po sprawdzeniu według zasady o nowych kluczach i tabelach. |
| Strony CMS (#32, #33) | Tabele migawki `ps_cms`, `ps_cms_lang`, `ps_cms_shop`, `ps_cms_category`, `ps_cms_category_lang`, `ps_cms_category_shop`, `ps_cms_role`, `ps_cms_role_lang` oraz klucz `PS_CONDITIONS_CMS_ID`. | Instalator. | Brak danych osobowych i sekretów. |
| Moduły | Nazwy i stany oraz pozycje w hakach według nazwy. Własne tabele modułu trafiają na listę dopiero po sprawdzeniu. | Instalator. | Brak danych osobowych i sekretów. |
| Motyw | `ps_shop.theme_name` przez `theme:enable`. Pliki trafiają do `shop/`. | Instalator. | Brak danych osobowych i sekretów. |
| Pliki | Klucze `PS_LOGO`, `PS_FAVICON`, `PS_STORES_ICON`, `PS_LOGO_INVOICE` i `PS_LOGO_MAIL` zawierają nazwy plików obrazów i trafiają na listę kluczy. Klucze `PS_LOGO_INVOICE` i `PS_LOGO_MAIL` pojawiają się dopiero po wgraniu logo faktury lub poczty w panelu. Logo, favicon i obrazy modułów to pliki w `shop/` (#12). Logo przewoźnika to plik `img/s/<id_carrier>.jpg` (`_PS_SHIP_IMG_DIR_`), a `Carrier.php` kopiuje je pod nowy id przy każdym zapisie przewoźnika. Nazwa pliku jest identyfikatorem z migawki, więc te pliki eksportujemy razem z migawką, a nie ręcznie. | Instalator, a `PS_LOGO_INVOICE` i `PS_LOGO_MAIL` panel po wgraniu logo. | Brak danych osobowych i sekretów. |
| Poczta (#14) | `PS_MAIL_METHOD`, `PS_MAIL_SERVER`, `PS_MAIL_SMTP_PORT` i `PS_MAIL_SMTP_ENCRYPTION` ustawia skrypt startowy z #14. Klucze `PS_MAIL_TYPE` i `PS_LOG_EMAILS` odtwarzamy po nazwie. | Instalator i skrypt startowy. | Brak danych osobowych i sekretów. |

`Install.php` nie ustawia `PS_CURRENCY_DEFAULT`, ale robi to paczka lokalizacyjna. W trybie instalacji `LocalizationPack::loadLocalisationPack` zapisuje w tym kluczu id waluty z paczki, jeśli paczka ma dokładnie jedną walutę. Paczka `pl.xml` ma tylko PLN, więc domyślną walutą jest PLN (sprawdzone w #31). Kraje pochodzą z `install-dev/data/xml/country.xml`. Źródło stref nie jest sprawdzone.

Klucz `PS_DETECT_COUNTRY` ma wartość 0, bo przy domyślnej wartości 1 sklep ustala kraj odwiedzającego z nagłówka `Accept-Language` (`FrontController::init`). Grupy podatkowe z `pl.xml` mają reguły tylko dla krajów UE, Monako i Wielkiej Brytanii. Przy przeglądarce `en-US` sklep bierze z nagłówka kod `US` (`Tools::getCountryIsoCodeFromHeader`), wybiera USA, które instalator tworzy jako aktywny kraj (`country.xml`), nie znajduje reguły dla USA i pokazuje ceny bez VAT. Na działającym stosie przeglądarka `en-US` widziała przy wartości 1 cenę netto, a przy 0 cenę brutto, tak jak `pl-PL`.

Tabela `ps_lang` nie jest wersjonowana i zostaje taka, jaką instalator tworzy z `PS_LANGUAGE=pl` i `PS_COUNTRY=pl` (`deploy/compose.yaml`), czyli z jednym językiem polskim. Instalator dodaje też języki z paczki lokalizacyjnej kraju, więc przy kodzie `PL` doszedłby angielski z `default.xml`. Dodanie języka pobiera pliki (`Language::downloadAndInstallLanguagePack`), co leży poza tym ADR.

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
| `PS_SHOP_EMAIL` i `PS_LOGS_EMAIL_RECEIVERS` | `ADMIN_MAIL` z `deploy/.env`. |
| `app/config/parameters.php` | Sekrety. Plik jest już ignorowany (`.gitignore:8`). |

Zamówienia, koszyki i adresy też są wykluczone, bo lista jest listą dozwolonych pozycji.

## Konsekwencje

- Eksport nie zawiera sekretów, jego diffy są czytelne, a jedna migawka pochłania dryf identyfikatorów.
- Po edycji przewoźnika albo używanego podatku w diffie pojawiają się nowe wiersze.
- Równoległe PR-y są ryzykiem. Git nie pokaże konfliktu, gdy eksport #35 wskazuje grupy podatkowe sprzed #31. Dlatego istnieje kolejność scalania i ponowny eksport.
- Identyfikatory, na które migawka wskazuje, ale których nie zawiera, zostają takie, jakie tworzy instalator. Ich stabilność to założenie. `ps_carrier_group` wskazuje `ps_group`. `link_block.id_hook` wskazuje `ps_hook`. Tabele `_lang` wskazują `ps_lang`. Tabele `_shop` wskazują sklep 1. Najsłabszym punktem są haki rejestrowane przez moduły.
- Wiersze tworzone później wskazują na migawkę. Import (#17) zapisuje `ps_product.id_tax_rules_group`. `link_block.content` zawiera identyfikatory kategorii i produktów. `MOD_BLOCKTOPMENU_ITEMS` prawdopodobnie zawiera identyfikatory kategorii, a ten format to założenie. Dlatego odtwarzanie działa przed #17, a #17 musi znajdować grupy podatkowe po nazwie i dawać te same identyfikatory kategorii w każdym czystym uruchomieniu.
- `bin/console` z poleceniem `prestashop:config` działa w obrazie, co sprawdziliśmy na stosach #14 i #31. To, czy `theme:enable` resetuje haki modułów, to założenie, które sprawdza #16.
- Pliki w `shop-data` nie są odświeżane z obrazu (`docs/adr/0003-container-architecture.md:69`).

## Źródła

Każde źródło sprawdzono na tagu 8.2.8, chyba że zaznaczono "gałąź 8.2.x", wersję modułu albo gałąź master. Zgodność wersji z gałęzi master z wersjami modułów w obrazie to założenie, które sprawdza #16.

- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/install-dev/data/db_structure.sql
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/install-dev/data/xml/configuration.xml
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/src/PrestaShopBundle/Install/Install.php (`configureShop`, `installDefaultData`)
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/localization/pl.xml
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/classes/tax/Tax.php (`update`, `historize`)
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/controllers/admin/AdminCarrierWizardController.php (`ajaxProcessFinishStep`)
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/src/Adapter/Invoice/InvoiceOptionsConfiguration.php
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/classes/Language.php
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/config/defines.inc.php
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/classes/Carrier.php
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/classes/pdf/HTMLTemplate.php
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/composer.json
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/src/PrestaShopBundle/Command/ConfigCommand.php
- gałąź 8.2.x: https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.x/src/PrestaShopBundle/Command/ModuleCommand.php
- gałąź 8.2.x: https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.x/src/PrestaShopBundle/Command/ThemeEnablerCommand.php
- gałąź 8.2.x: https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.x/classes/webservice/WebserviceRequest.php (`getResources`)
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/classes/Mail.php
- gałąź 8.2.x: https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.x/classes/shop/Shop.php
- https://raw.githubusercontent.com/PrestaShop/ps_linklist/v6.0.7/src/Repository/LinkBlockRepository.php
- https://raw.githubusercontent.com/PrestaShop/ps_cashondelivery/v2.0.1/ps_cashondelivery.php
- https://raw.githubusercontent.com/PrestaShop/ps_wirepayment/v2.2.0/ps_wirepayment.php
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/composer.lock (wersja `ps_wirepayment`)
- https://raw.githubusercontent.com/PrestaShop/ps_mainmenu/master/ps_mainmenu.php
- https://raw.githubusercontent.com/PrestaShop/ps_searchbar/master/ps_searchbar.php
- https://raw.githubusercontent.com/PrestaShop/ps_emailsubscription/master/ps_emailsubscription.php
- https://github.com/PrestaShop/psgdpr/tree/master/sql/install
- https://mariadb.com/kb/en/mariadb-dump/
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/classes/LocalizationPack.php (`loadLocalisationPack`)
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/src/PrestaShopBundle/Cache/LocalizationWarmer.php (`warmUp`)
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/localization/default.xml
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/install-dev/classes/datas.php
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/install-dev/data/xml/group.xml
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/install-dev/data/xml/country.xml
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/classes/Country.php (`getByIso`)
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/classes/controller/FrontController.php (`init`)
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/classes/Tools.php (`getCountryIsoCodeFromHeader`)
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/classes/Address.php (`initialize`)
- https://raw.githubusercontent.com/PrestaShop/PrestaShop/8.2.8/src/Adapter/Localization/LocalizationConfiguration.php
- gałąź master: https://raw.githubusercontent.com/PrestaShop/docker/master/base/config_files/docker_run.sh
