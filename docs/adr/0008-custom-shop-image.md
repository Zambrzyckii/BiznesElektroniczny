# ADR 0008: Własny obraz sklepu

- **Status:** zaakceptowana
- **Data:** 2026-11-17

## Kontekst

Wymaganie W3 [K] mówi, że sklep działa w kontenerach Docker. W etapie 2 ten sam sklep trafi na klaster, który działa na amd64. Motyw potomny i moduły własne mają leżeć w `shop/` i być zamknięte w jednej wersji obrazu.

- Obraz `prestashop/prestashop:8.2.8-8.1-apache` rozpakowuje PrestaShop do `/tmp/data-ps/`. Nie ma w nim `COPY` do `/var/www/html`, `VOLUME` ani `CMD`. Polecenie `CMD ["/tmp/docker_run.sh"]` pochodzi z obrazu bazowego `prestashop/base:8.1-apache`.
- Skrypt `docker_run.sh` kopiuje `/tmp/data-ps/prestashop/` do `/var/www/html` przez `cp -n` tylko przy pierwszej instalacji. Dzieje się tak, gdy brakuje `settings.inc.php`, `parameters.php` i `install.lock`.
- Skrypty z `/tmp/init-scripts/` skrypt startowy uruchamia przy każdym starcie, jako root, pod `set -e`, tuż przed serwerem WWW. Przy świeżej instalacji kolejność to instalator, `post-install-scripts`, a potem `init-scripts`.
- `/var/www/html` jest nazwanym wolumenem `shop-data` (ADR 0003). Docker wypełnia go zawartością obrazu tylko przy pierwszym utworzeniu, więc pliki z nowego obrazu nie podmienią się w istniejącym wolumenie.
- Tag `8.2.8-8.1-apache` jest wieloarchitekturowy (amd64, arm64, arm/v7). Bez przypięcia platformy Mac z Apple Silicon zbuduje obraz arm64.
- Poza zakresem tej decyzji jest wygląd motywu potomnego (#37). Sposób jego aktywacji opisuje sekcja „Aktywacja motywu potomnego”.

## Rozważane opcje

### Dostarczenie plików do sklepu

| Opcja | Zalety | Wady |
|---|---|---|
| **Kopia w obrazie i skrypt w `init-scripts` (wybrana)** | Pliki są w obrazie, więc etap 2 dostaje komplet w jednej wersji. Skrypt odświeża wolumen przy każdym starcie. | Plik usunięty z repozytorium zostaje w wolumenie. Zmiany tych plików zrobione w panelu są nadpisywane. |
| Bind mount `shop/themes` i `shop/modules` | Zmiana pliku jest widoczna od razu. | Obraz nie zawiera plików, więc etap 2 nie dostaje wersjonowanego obrazu. |
| Osobne wolumeny na motyw i moduły zamiast `shop-data` | Wolumen z samymi danymi nie przykrywa plików obrazu. | Przepisuje ADR 0003 i grozi utratą plików, które PrestaShop zapisuje w `/var/www/html`. |
| `COPY` prosto do `/var/www/html` | Najprostszy plik. | Trafia tylko do nowego wolumenu, bo istniejący przykrywa obraz. |

### Platforma obrazu

| Opcja | Zalety | Wady |
|---|---|---|
| **`platform: linux/amd64` w compose (wybrana)** | Działa tak samo na każdym komputerze, a obraz jest zgodny z klastrem. | Na Apple Silicon sklep działa w emulacji. |
| Flaga `--platform` przy budowaniu | Nie zmienia pliku compose. | Compose na Macu nadal zbudowałby arm64, a uruchomienie obrazu amd64 wymagałoby osobnej flagi. |

### Przebudowa obrazu

| Opcja | Zalety | Wady |
|---|---|---|
| **`pull_policy: build` w usłudze `shop` (wybrana)** | Każde `up` buduje obraz, więc motyw z repozytorium zawsze trafia do sklepu. Komenda w README się nie zmienia. | Każde `up` uruchamia budowanie. Dzięki cache warstw jest ono szybkie, gdy pliki się nie zmieniły. |
| Flaga `--build` w README | Budowanie tylko na życzenie. | Łatwo ją pominąć i zostać ze starym motywem. |

### Aktywacja motywu potomnego

| Opcja | Zalety | Wady |
|---|---|---|
| **Skrypt `20-enable-theme.sh` w `shop/init-scripts/`, który wywołuje `prestashop:theme:enable` tylko, gdy `ps_shop.theme_name` wskazuje inny motyw (wybrana)** | Skrypt jest w obrazie, więc działa też w etapie 2. Motyw włącza PrestaShop, tak jak zakłada ADR 0006 z PR-a #56. Kolejny start nie zmienia ustawień. | Skrypt czyta bazę klientem `mysql` z obrazu. |
| Ten sam skrypt bez sprawdzenia | Krótszy skrypt. | `ThemeManager::enable` nie sprawdza, czy motyw jest już aktywny. Przy każdym starcie układa moduły w hakach według `theme.yml` i włącza moduły wyłączone w panelu (źródło: [`ThemeManager.php`](https://github.com/PrestaShop/PrestaShop/blob/8.2.8/src/Core/Addon/Theme/ThemeManager.php) i [`HookConfigurator.php`](https://github.com/PrestaShop/PrestaShop/blob/8.2.8/src/Core/Module/HookConfigurator.php) w tagu 8.2.8). |
| `UPDATE` kolumny `ps_shop.theme_name` w SQL | Bez `bin/console`. | Pomija kroki włączania motywu (moduły, haki, typy obrazów) i omija wybór z ADR 0006. |
| Skrypt w `deploy/init-scripts/` montowany w compose | Ta sama konwencja co skrypty z kluczami z #14 i #31. | Motyw jest w obrazie, a skrypt nie. Wymaga zmiany compose, a klaster w etapie 2 nie ma repozytorium. |

## Decyzja

Wybieramy własny obraz sklepu zbudowany z `shop/Dockerfile`. Dodajemy pliki z tabeli.

| Plik | Rola |
|---|---|
| `shop/Dockerfile` | Bazuje na `prestashop/prestashop:8.2.8-8.1-apache` i kopiuje pliki do obrazu. Nie ma `RUN`, `CMD`, `ENTRYPOINT` ani `VOLUME`, więc `CMD` z obrazu bazowego zostaje. |
| `shop/init-scripts/10-copy-shop-files.sh` | Przy każdym starcie kopiuje `themes/` i `modules/` do `/var/www/html` i ustawia właściciela `www-data`. |
| `shop/init-scripts/20-enable-theme.sh` | Przy każdym starcie sprawdza `ps_shop.theme_name` i włącza motyw potomny przez `prestashop:theme:enable`, gdy aktywny jest inny motyw (#37). |
| `shop/themes/.gitkeep` i `shop/modules/.gitkeep` | Utrzymują puste katalogi w repozytorium. |
| `.gitattributes` | Wymusza końce linii LF w plikach `*.sh`, bo skrypt z CRLF nie uruchomi się w kontenerze. |

Przyjmujemy następujące zasady.

- Pliki czekają w obrazie w `/tmp/shop-files/`, a skrypt kopiuje je stamtąd do wolumenu `shop-data`.
- Skrypty w `shop/init-scripts/` mają numeryczny prefiks. `10-` i `20-` są zajęte, a kolejne skrypty dostają wyższe numery i uruchamiają się po nich.
- Kopiowanie robimy bez `-p`, więc każdy kopiowany plik dostaje nowy czas modyfikacji przy każdym starcie. Po każdym restarcie Smarty kompiluje od nowa wszystkie szablony motywu.
- Katalog motywu nie może nazywać się `classic`, bo skrypt nadpisałby domyślny motyw PrestaShop.
- Usługa `shop` w `deploy/compose.yaml` ma `build: ../shop`, `platform: linux/amd64` i `pull_policy: build`, a nie ma klucza `image`.

## Konsekwencje

- Plik usunięty z repozytorium zostaje w wolumenie `shop-data` aż do `down -v`, bo skrypt tylko dopisuje i nadpisuje pliki.
- Zmiany plików motywu i modułów własnych zrobione w panelu znikają przy następnym starcie kontenera.
- Aktywacja motywu (#37) to skrypt `20-enable-theme.sh` w `init-scripts`, a nie w `post-install-scripts`. Przy świeżej instalacji `post-install-scripts` działają przed `init-scripts`, więc motywu nie byłoby jeszcze w wolumenie. Skrypt włącza motyw tylko wtedy, gdy w bazie aktywny jest inny, więc nie nadpisuje pozycji modułów w hakach, które odtwarza #16.
- Zmiana `config/theme.yml` motywu potomnego nie trafia do istniejącego wolumenu. `ThemeRepository::getInstanceByName` czyta kopię z `config/themes/<nazwa>/shop1.json` i zapisuje ją tylko, gdy jej brakuje. Zmiana działa po `down -v`.
- Skopiowanie modułu do `modules/` go nie instaluje. Instalacja wymaga osobnego kroku.
- Na Apple Silicon sklep działa w emulacji, więc start i budowanie trwają dłużej.
- Każde `up` uruchamia budowanie obrazu.
- Etap 2 będzie potrzebował nazwy `image:` z rejestrem, bo klaster nie zbuduje obrazu z katalogu `shop/`.
