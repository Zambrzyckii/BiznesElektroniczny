# ADR 0003: Architektura kontenerów sklepu

- **Status:** zaakceptowana
- **Data:** 2026-11-17
- **Uwaga:** [ADR 0007](0007-https-proxy.md) zastępuje port `8080:80` i domenę `localhost:8080` z tego dokumentu. Sklep jest dostępny tylko przez proxy HTTPS.

## Kontekst

Wymaganie W3 [K] mówi, że sklep działa w kontenerach Docker Compose v2 i startuje z czystego klona jedną komendą.

- Obraz `prestashop/prestashop:8.2.8-8.1-apache` jest przypięty, bo tag `latest` wskazuje już PrestaShop 9.
- Obraz nie zawiera bazy danych ani healthchecka. Jego skrypt startowy instaluje sklep, gdy `PS_INSTALL_AUTO=1`.
- PrestaShop zapisuje domenę sklepu w bazie podczas instalacji.
- Poza zakresem tej decyzji są własny obraz sklepu (#12), HTTPS (#13), Mailpit (#14) i ładowanie danych (#17).

## Rozważane opcje

### Baza danych

| Opcja | Zalety | Wady |
|---|---|---|
| **MariaDB 10.11 (wybrana)** | Wsparcie LTS do 2028-02-16. Ta sama linia co klient `mariadb-client` 10.11, którym obraz sklepu czeka na bazę. | Krótsze wsparcie niż w 11.4. |
| MariaDB 11.4 | Wsparcie LTS do 2029-05-29. | Nowsza niż klient w obrazie sklepu, a wymagania PrestaShop 8 podają tylko minimum MariaDB 10.2. |
| MySQL 8.0 | Issue dopuszcza tę bazę. | README PrestaShop/docker uruchamia MySQL z `--default-authentication-plugin=mysql_native_password`, więc potrzebna jest dodatkowa konfiguracja, a klient w obrazie sklepu to MariaDB. |

### Miejsce danych

| Opcja | Zalety | Wady |
|---|---|---|
| **Nazwane wolumeny `db-data` i `shop-data` (wybrana)** | Dane są poza repozytorium. Docker kopiuje pliki sklepu z obrazu do pustego wolumenu. Polecenie `down -v` daje czysty start. | Pliki sklepu nie są widoczne w repozytorium, a zmieniony obraz nie trafia do istniejącego wolumenu. |
| Bind mount do katalogu w repozytorium | Pliki widać w edytorze. | Dane leżą w katalogu repozytorium wbrew kryterium issue i grozi ich commit. |
| Bez wolumenów | Najprostszy plik. | Usunięcie kontenera kasuje bazę i sklep. |

### Przekazanie haseł

| Opcja | Zalety | Wady |
|---|---|---|
| **Interpolacja `${ZMIENNA:?komunikat}` w `environment` (wybrana)** | Każda usługa dostaje tylko swoje zmienne, a brak `.env` kończy się czytelnym błędem. | Zmienna `DB_PASSWD` występuje w dwóch usługach. |
| `env_file: .env` | Krótszy plik. | Każda usługa dostaje wszystkie zmienne, także hasło roota bazy w kontenerze sklepu. |

### Domena sklepu

| Opcja | Zalety | Wady |
|---|---|---|
| **Stałe `PS_DOMAIN=localhost:8080` (wybrana)** | Adresy są przewidywalne i nic nie nadpisuje bazy w trakcie działania sklepu. | Inny port po instalacji wymaga zmiany domeny w sklepie albo reinstalacji. |
| `PS_HANDLE_DYNAMIC_DOMAIN=1` | Sklep dopasowuje się do nagłówka Host. | Plik `docker_updt_ps_domains.php` staje się DirectoryIndex Apache i zapisuje nową domenę w bazie przy każdym innym hoście, więc błędny adres po cichu zmienia domenę sklepu. |
| Bez `PS_DOMAIN` | Mniej konfiguracji. | Skrypt startowy ustawia domenę na IP kontenera, więc linki w przeglądarce nie działają. |

## Decyzja

Wybieramy dwie usługi opisane w `deploy/compose.yaml`.

| Usługa | Obraz | Wolumen | Port na hoście | Healthcheck |
|---|---|---|---|---|
| `db` | `mariadb:10.11` | `db-data:/var/lib/mysql` | brak | `healthcheck.sh --connect --innodb_initialized` |
| `shop` | `prestashop/prestashop:8.2.8-8.1-apache` | `shop-data:/var/www/html` | `8080:80` | brak katalogu `install` i odpowiedź serwera WWW |

Przyjmujemy następujące zasady.

- Sklep startuje dopiero, gdy `db` jest zdrowa, przez `depends_on` z `condition: service_healthy`.
- Instalacja przebiega automatycznie po polsku dzięki `PS_INSTALL_AUTO=1`, `PS_LANGUAGE=pl` i `PS_COUNTRY=PL`.
- Hasła i dane administratora są tylko w `deploy/.env`, a repozytorium zawiera `deploy/.env.example`. Plik leży obok `compose.yaml`, bo Compose czyta `.env` z katalogu pliku podanego w `-f`.
- Plik nie ma kluczy `version`, `name` ani `container_name`. Projekt nazywa się `deploy`, a osobny projekt można uruchomić z `COMPOSE_PROJECT_NAME`.
- Baza nie publikuje portu na hoście.

## Konsekwencje

- Wartości z `.env` działają tylko przy pierwszym starcie. MariaDB tworzy użytkownika i hasło tylko w pustym katalogu danych, a sklep instaluje się raz. Zmiana wymaga `down -v`, które usuwa dane. Zmiana samego `DB_PASSWD` sprawia, że skrypt startowy sklepu czeka na bazę bez końca.
- Domena jest zapisana w bazie jako `PS_SHOP_DOMAIN`, `PS_SHOP_DOMAIN_SSL` i adres sklepu (`ShopUrl`). Inny port, HTTPS (#13) albo klaster w etapie 2 wymagają zmiany domeny albo reinstalacji.
- Po pierwszym starcie `shop-data` przykrywa pliki z obrazu. Przy własnym obrazie (#12) zmiany obrazu nie trafią do istniejącego wolumenu.
- Instalator wgrywa produkty demonstracyjne, bo domyślnie ma `fixtures=1`, a skrypt obrazu nie przekazuje tej opcji. Trzeba je usunąć przy imporcie danych (#17).
- Pierwszy start trwa kilka minut, dlatego healthcheck sklepu ma `start_period` równe 10 minut.
- Przerwana pierwsza instalacja zostawia `install.lock`, a kontener sklepu kończy się wtedy kodem 42. Rozwiązaniem jest `down -v`.
- Stały port 8080 blokuje start, gdy inny program na komputerze już go używa.
