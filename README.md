# Sklep dobrakaloria.pl na PrestaShop

Projekt zespołowy z przedmiotu Biznes Elektroniczny. Odtwarzamy sklep internetowy [dobrakaloria.pl](https://dobrakaloria.pl/) na platformie PrestaShop uruchamianej w kontenerach Docker. W etapie 1 powstają scraper danych ze sklepu źródłowego, sklep z zaimportowanymi produktami i testy E2E. W etapie 2 ten sam sklep trafi na klaster Docker Swarm.

Projekt ma charakter edukacyjny i nie jest powiązany z właścicielem sklepu dobrakaloria.pl.

## Wersje

- PrestaShop 8.2.8
- Obraz Dockera `prestashop/prestashop:8.2.8-8.1-apache` z PHP 8.1

## Uruchomienie

Instrukcja krok po kroku powstanie razem z plikiem `deploy/compose.yaml` w issue [#11](https://github.com/Zambrzyckii/BiznesElektroniczny/issues/11).

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
