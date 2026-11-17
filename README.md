# Sklep dobrakaloria.pl na PrestaShop

Projekt zespołowy z przedmiotu Biznes Elektroniczny. Odtwarzamy sklep internetowy [dobrakaloria.pl](https://dobrakaloria.pl/) na platformie PrestaShop uruchamianej w kontenerach Docker. W etapie 1 powstają scraper danych ze sklepu źródłowego, sklep z zaimportowanymi produktami i testy E2E. W etapie 2 ten sam sklep trafi na klaster Docker Swarm.

Projekt ma charakter edukacyjny i nie jest powiązany z właścicielem sklepu dobrakaloria.pl.

## Wersje

- PrestaShop 8.2.8
- Obraz Dockera `prestashop/prestashop:8.2.8-8.1-apache` z PHP 8.1
- MariaDB 10.11 (obraz `mariadb:10.11`)

## Uruchomienie

Potrzebny jest Docker z Docker Compose v2. Wszystkie komendy uruchamiamy z katalogu głównego repozytorium.

1. Skopiuj plik ze zmiennymi i wpisz w nim własne hasła. Hasło administratora musi mieć od 8 do 72 znaków.

   ```bash
   cp deploy/.env.example deploy/.env
   ```

2. Uruchom sklep.

   ```bash
   docker compose -f deploy/compose.yaml up -d --wait
   ```

Pierwsze uruchomienie pobiera obrazy i instaluje sklep po polsku bez kreatora, co może potrwać kilka minut. Komenda kończy się, gdy baza i sklep są gotowe. Instalacja wgrywa też produkty demonstracyjne PrestaShop.

- Sklep: http://localhost:8080
- Panel administracyjny: `http://localhost:8080/<PS_FOLDER_ADMIN>/`, logowanie wartościami `ADMIN_MAIL` i `ADMIN_PASSWD` z `deploy/.env`

Compose szuka pliku `.env` w katalogu pliku podanego w `-f`, dlatego plik leży w `deploy/`. Pozostałe komendy, np. `ps`, `logs` i `down`, też wymagają `-f deploy/compose.yaml` i pliku `deploy/.env`.

Dane bazy i plików sklepu leżą w nazwanych wolumenach Dockera, a nie w katalogu repozytorium. Komenda `docker compose -f deploy/compose.yaml down` zatrzymuje sklep i zachowuje dane. Wartości z `deploy/.env` działają tylko przy pierwszej instalacji. Żeby je zmienić, zacząć od czystego sklepu albo powtórzyć przerwaną pierwszą instalację, uruchom `docker compose -f deploy/compose.yaml down -v`, a potem komendę z kroku 2. Opcja `-v` usuwa wszystkie dane sklepu.

## Struktura repozytorium

| Katalog | Zawartość |
|---|---|
| `shop/` | Kod sklepu, motyw i moduły własne, Dockerfile, teksty stron CMS w `shop/cms/` do wklejenia w panelu |
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
