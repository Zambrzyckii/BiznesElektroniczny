# Sklep dobrakaloria.pl na PrestaShop

Projekt zespołowy z przedmiotu Biznes Elektroniczny. Odtwarzamy sklep internetowy [dobrakaloria.pl](https://dobrakaloria.pl/) na platformie PrestaShop uruchamianej w kontenerach Docker. W etapie 1 powstają scraper danych ze sklepu źródłowego, sklep z zaimportowanymi produktami i testy E2E. W etapie 2 ten sam sklep trafi na klaster Docker Swarm.

Projekt ma charakter edukacyjny i nie jest powiązany z właścicielem sklepu dobrakaloria.pl.

## Wersje

- PrestaShop 8.2.8
- Obraz Dockera `prestashop/prestashop:8.2.8-8.1-apache` z PHP 8.1
- MariaDB 10.11 (obraz `mariadb:10.11`)
- Mailpit 1.34.0 (obraz `axllent/mailpit:v1.34.0`)

## Uruchomienie

Potrzebny jest Docker z Docker Compose v2. Wszystkie komendy uruchamiamy z katalogu głównego repozytorium.

1. Skopiuj plik ze zmiennymi i wpisz w nim własne hasła oraz klucz `PS_WS_KEY` (32 znaki alfanumeryczne). Hasło administratora musi mieć od 8 do 72 znaków.

   ```bash
   cp deploy/.env.example deploy/.env
   ```

2. Uruchom sklep.

   ```bash
   docker compose -f deploy/compose.yaml up -d --wait
   ```

   Po świeżej instalacji sklep ma ustawienia z repozytorium dopiero po `sh deploy/restore-settings.sh`, opisanym w podrozdziale "Jak odtworzyć ustawienia" sekcji "Ustawienia sklepu".

Pierwsze uruchomienie pobiera obrazy i instaluje sklep po polsku bez kreatora, co może potrwać kilka minut. Komenda kończy się, gdy baza i sklep są gotowe. Instalacja wgrywa też produkty demonstracyjne PrestaShop.

- Sklep: http://localhost:8080
- Panel administracyjny: `http://localhost:8080/<PS_FOLDER_ADMIN>/`, logowanie wartościami `ADMIN_MAIL` i `ADMIN_PASSWD` z `deploy/.env`
- Interfejs WWW Mailpit z pocztą wysłaną przez sklep: http://localhost:8025

Compose szuka pliku `.env` w katalogu pliku podanego w `-f`, dlatego plik leży w `deploy/`. Pozostałe komendy, np. `ps`, `logs` i `down`, też wymagają `-f deploy/compose.yaml` i pliku `deploy/.env`.

Dane bazy i plików sklepu leżą w nazwanych wolumenach Dockera, a nie w katalogu repozytorium. Komenda `docker compose -f deploy/compose.yaml down` zatrzymuje sklep i zachowuje dane. Wartości z `deploy/.env` działają tylko przy pierwszej instalacji. Żeby je zmienić, zacząć od czystego sklepu albo powtórzyć przerwaną pierwszą instalację, uruchom `docker compose -f deploy/compose.yaml down -v`, a potem komendę z kroku 2. Opcja `-v` usuwa wszystkie dane sklepu.

Cała poczta sklepu trafia do Mailpit i nigdy na prawdziwe adresy. Ustawienia SMTP zapisuje skrypt `deploy/init-scripts/configure-mail.sh` przy starcie kontenera sklepu, więc nie wyklikujemy ich ręcznie. Mailpit trzyma wiadomości tylko do restartu swojego kontenera, dlatego nie restartuj go między rejestracją konta a pokazaniem wiadomości powitalnej. Port 8025 na hoście musi być wolny.
### Konfiguracja Webservice i import kategorii

Gdy sklep jest uruchomiony, włącz Webservice API i zaimportuj drzewo kategorii (wymaga zależności z `scraper/requirements.txt`). Oba polecenia odczytują `PS_WS_KEY` (32 znaki alfanumeryczne) ze zmiennych środowiskowych powłoki - zapisz go w `deploy/.env` i wyeksportuj w powłoce (np. `export PS_WS_KEY=...`).

1. Włącz Webservice i nadaj kluczowi uprawnienia do zasobu `categories` (`GET`, `POST`, `PUT`):

   ```bash
   ./deploy/setup-webservice.sh
   ```

2. Zaimportuj kategorie z `scraper-results/categories.json`:

   ```bash
   python scraper/import_categories.py
   ```

Skrypt `scraper/import_categories.py` używa `PS_WS_KEY` i opcjonalnie `PS_SHOP_URL` (domyślnie `http://localhost:8080`). Ścieżkę do pliku i adres sklepu można też podać flagami `--categories` i `--shop-url`. Oba polecenia są idempotentne i można je uruchamiać wielokrotnie.

## Ustawienia sklepu

Ustawienia z "Listy ustawień" w `docs/adr/0006-settings-versioning.md` leżą w repozytorium, w katalogu `deploy/settings/`. Eksport zapisuje je do plików, a odtwarzanie wgrywa je z powrotem do sklepu.

| Plik w `deploy/settings/` | Zawartość |
|---|---|
| `tables.txt` | Lista tabel w migawce. Jest listą dozwolonych pozycji, ręcznie edytowaną |
| `config-keys.txt` | Lista kluczy konfiguracji. Jest listą dozwolonych pozycji, ręcznie edytowaną |
| `snapshot.sql` | Migawka tabel z `tables.txt`, wiersz po wierszu, z opróżnieniem każdej tabeli przed wstawieniem |
| `config.tsv` | Wartości kluczy z `config-keys.txt`, a dla wartości per język także kod języka |
| `modules.tsv` | Nazwy modułów i ich stan, włączony lub wyłączony |
| `theme.txt` | Nazwa motywu |
| `hook-positions.sql` | Pozycje modułów w hakach, zapisane przez nazwy modułów i haków |
| `payment-restrictions.sql` | Ograniczenia płatności według przewoźników, krajów i walut, zapisane przez nazwę modułu |
| `carrier-logos/` | Pliki logo przewoźników, które odpowiadają identyfikatorom z migawki |

Nowa tabela albo nowy klucz trafia do `tables.txt` lub `config-keys.txt` w tym samym PR, po sprawdzeniu, że nie zawiera danych osobowych ani sekretu. Eksport zapisuje tylko pozycje z "Listy ustawień" w ADR 0006, więc nie zawiera danych klientów, haseł, kluczy API ani wartości z `deploy/.env`.

### Kiedy eksportować

Po każdej zmianie ustawienia z listy. Konfigurujesz sklep na stosie odbudowanym z aktualnego `main`, a potem eksportujesz. Zawsze eksportujesz wszystko, nigdy jeden obszar. Zasady opisuje ADR 0006, sekcja "Jak zapisujemy zmiany ustawień".

### Jak eksportować

1. Zacznij od świeżego stosu z aktualnego `main`. Usuń stos razem z wolumenami, uruchom go ponownie jak w kroku 2 sekcji "Uruchomienie" i odtwórz ustawienia. Opcja `-v` usuwa wszystkie dane sklepu w tym stosie.

   ```bash
   docker compose -f deploy/compose.yaml down -v
   docker compose -f deploy/compose.yaml up -d --wait
   sh deploy/restore-settings.sh
   ```

   Dopiero potem zmień ustawienia w panelu.
2. Z katalogu głównego repozytorium uruchom eksport.

   ```bash
   sh deploy/export-settings.sh
   ```

3. Obejrzyj zmiany.

   ```bash
   git diff deploy/settings
   ```

   Jeśli w diffie jest zmieniona tabela spoza Twojego obszaru, wyeksportuj ponownie ze stosu odtworzonego z `main`.
4. Przed commitem sprawdź katalog gitleaksem. W wersji 8.19 i nowszych użyj `gitleaks dir deploy/settings`, w starszych `gitleaks detect --no-git --source deploy/settings`.

Eksport przerywa się z błędem, jeśli któryś klucz z listy ma wartość ustawioną dla jednego sklepu albo grupy sklepów, bo wtedy nie trafiłby do pliku.

### Jak odtworzyć ustawienia

Na działającym stosie uruchom odtwarzanie.

```bash
sh deploy/restore-settings.sh
```

Robisz to po pierwszej instalacji, po `down -v` i po awarii. Tabele z `snapshot.sql` są opróżniane i wypełniane od nowa, a pozycje w hakach i ograniczenia płatności sklepu o id 1 są usuwane i wgrywane z plików. Klucz z `config-keys.txt` jest ustawiany tylko wtedy, gdy ma wiersz w `config.tsv`. Eksport pomija klucze bez wiersza i z wartością NULL, więc taki klucz zachowuje na docelowym stosie swoją bieżącą wartość. Trwa kilka minut, bo każdy klucz ustawia osobne wywołanie `bin/console`. Skrypt włącza motyw, instaluje i włącza albo wyłącza moduły, wgrywa migawkę, zastępuje wszystkie logo przewoźników w sklepie plikami z repozytorium, ustawia klucze, wgrywa pozycje w hakach i ograniczenia płatności, a na końcu czyści cache. Nigdy nie odinstalowuje modułów. Żeby wyłączyć moduł, wyłącz go w sklepie i wyeksportuj ponownie. Moduł zainstalowany tylko na docelowym stosie, którego nie ma w `modules.tsv`, nie jest odinstalowywany ani wyłączany, ale traci pozycje w hakach, bo odtwarzanie usuwa wszystkie wiersze `ps_hook_module` sklepu przed wgraniem zapisanych. Ponowny eksport pokaże taki moduł w `modules.tsv`.

Po odtworzeniu sprawdź wynik. Uruchom eksport jeszcze raz, a potem `git status --porcelain deploy/settings`. Puste wyjście oznacza, że sklep ma ustawienia z repozytorium. Samo `git diff` pomija pliki nieśledzone, więc nie wykryłoby logo przewoźnika, którego brakuje w repozytorium.

### Wymagania

- Działający stos z `deploy/compose.yaml` i plik `deploy/.env`.
- Powłoka POSIX `sh`, czyli Linux, macOS albo WSL.
- Skrypty same przechodzą do katalogu `deploy/`. Przy nazwie stosu innej niż domyślna ustaw najpierw `COMPOSE_PROJECT_NAME`.

## Struktura repozytorium

| Katalog | Zawartość |
|---|---|
| `shop/` | Kod sklepu, motyw i moduły własne, Dockerfile |
| `scraper/` | Scraper i jego testy |
| `scraper-results/` | Wyniki scrapowania w UTF-8 z adresami zdjęć i do 20 przykładowych zdjęć |
| `tests/` | Testy E2E w Playwright |
| `deploy/` | `compose.yaml` oraz skrypty instalacji, inicjalizacji danych, backupu i odtwarzania |
| `docs/` | Dziennik AI w `AI_LOG.md` i decyzje architektoniczne w `docs/adr/` |

## Zespół

| Imię i nazwisko | GitHub |
|---|---|
| Bartosz Zambrzycki | [@Zambrzyckii](https://github.com/Zambrzyckii) |
| Mateusz Zbiciak | [@maatiZzz](https://github.com/maatiZzz) |
| Iga Pawłowska | [@czlowiek2650](https://github.com/czlowiek2650) |
| Oliwia Pawlędzio | [@SuperAkara](https://github.com/SuperAkara) |

## Sposób pracy

Zasady pracy z gałęziami, pull requestami i recenzjami opisuje [CONTRIBUTING.md](CONTRIBUTING.md). Każde użycie narzędzi AI zapisujemy w [docs/AI_LOG.md](docs/AI_LOG.md).

### Issues

Issues etapu 1 rozpisaliśmy na starcie projektu, idąc po kolei przez wymagania prowadzącego. Traktujemy je jako plan startowy, który aktualizujemy, bo wtedy trudno było ocenić, co okaże się problemem w trakcie pracy. Gdy zakres zadania się zmienia, osoba przypisana poprawia opis issue i dopisuje komentarz z powodem zmiany. Issue, które straciło sens, zamykamy jako „not planned” z komentarzem o powodzie i nie usuwamy go, żeby historia planu została czytelna. Nowe problemy zgłaszamy jako nowe issues, a każde zrealizowane issue kończy się scalonym PR-em.
