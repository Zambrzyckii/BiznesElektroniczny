# Zasady współpracy

Ten plik opisuje, jak pracujemy w repozytorium. Zasady wynikają z wymagań przedmiotu i z konfiguracji repozytorium na GitHubie.

## Język

Kod, nazwy plików, commity, gałęzie i tytuły PR piszemy po angielsku. Opisy issues i PR-ów, recenzje oraz dokumentację piszemy po polsku.

## Issues

- Każde zadanie ma swoje issue. Nowe issue zakładamy z szablonu „Zadanie”.
- Zanim zaczniesz pracę, przypisz issue do siebie. Nie pracujemy nad issue bez przypisanej osoby.
- Gdy zakres się zmienia, popraw opis issue i dodaj komentarz z powodem zmiany.
- Issue, które straciło sens, zamknij jako „not planned” z komentarzem o powodzie. Jeśli zastąpiło je inne issue, dodaj do niego link. Issues nie usuwamy.

## Gałęzie

- Nazwa gałęzi to numer issue i krótki opis po angielsku, np. `12-add-shop-dockerfile`. W tym formacie nazwę podpowiada GitHub, gdy tworzysz gałąź ze strony issue (Development, Create a branch).
- Gałąź tworzymy z aktualnego `main`.
- Gałęzie `live/<login>` są zarezerwowane dla modyfikacji na żywo podczas odbioru i nie trafiają do `main`.
- Do `main` nie wypychamy niczego bezpośrednio. Ochrona gałęzi blokuje push i force push także administratorowi.

## Tytuły PR i commity

- PR scalamy wyłącznie przez Squash and merge. Cały PR staje się jednym commitem w `main`, a jego tytułem jest tytuł PR-a z dopiskiem `(#N)`.
- Tytuł PR-a to jedno zdanie po angielsku w trybie rozkazującym, od 3 do 8 słów, z wielką literą na początku i bez kropki, np. `Add shop Dockerfile for linux/amd64`. Tytuły issues spełniają te zasady, więc najprościej użyć tytułu issue.
- Commity na gałęzi mogą być robocze, bo po scaleniu zostaje z nich tylko tytuł PR-a.

## Pull requesty

- Jeden PR zamyka jedno issue. W opisie wpisz `Closes #N`, żeby scalenie zamknęło issue automatycznie.
- Opis wypełniamy według szablonu, łącznie z polami „Jak zweryfikowano” i „Czy użyto AI”.
- Niedokończoną pracę otwieramy jako draft PR. O recenzję prosimy dopiero po kliknięciu Ready for review.
- Po akceptacji autor sam scala swój PR, bo to on odpowiada za rozwiązanie wszystkich komentarzy. Gdy powstanie CI ([#3](https://github.com/Zambrzyckii/BiznesElektroniczny/issues/3)), scalamy tylko PR, dla którego pipeline zakończył się sukcesem.
- PR, który zmienia sposób uruchamiania sklepu, aktualizuje sekcję „Uruchomienie” w README.
- PR, który dodaje generowane pliki, np. wyniki, zdjęcia, raporty lub kopie zapasowe, dopisuje je do `.gitignore`.

## Recenzje

- PR wymaga akceptacji jednej osoby innej niż autor.
- Każdy z nas musi w etapie być autorem co najmniej 3 i recenzentem co najmniej 3 scalonych PR-ów. Recenzentem może być dowolna osoba z zespołu. Swoją liczbę recenzji sprawdzisz na liście PR filtrem `is:pr is:merged reviewed-by:<login>`.
- Recenzent odpowiada w ciągu 48 godzin od prośby o recenzję.
- Recenzja zawiera co najmniej jeden merytoryczny komentarz, np. pytanie o decyzję, wskazanie ryzyka albo opis tego, jak recenzent sprawdził zmianę. Sama akceptacja nie wystarcza.

## Narzędzia AI

- PR z istotnymi fragmentami wygenerowanymi przez AI dostaje etykietę `ai-assisted`, a jego opis mówi, jak sprawdzono poprawność.
- Kto korzystał z narzędzia AI, dodaje wpis do [docs/AI_LOG.md](docs/AI_LOG.md) w tym samym PR-ze. Minimum to 2 wpisy na osobę w etapie.
- Do narzędzi AI nie wklejamy haseł, kluczy API ani danych dostępowych.
- Za każdą linię kodu odpowiada zespół. Na obronie trzeba umieć wyjaśnić także kod napisany z pomocą AI.

## Sekrety i duże pliki

- Hasła i klucze trzymamy w pliku `.env`, który nie trafia do repozytorium. W repozytorium jest tylko `.env.example` z przykładowymi wartościami.
- Prowadzący sprawdza całą historię repozytorium narzędziem gitleaks. Wypchnięty sekret zostaje w historii nawet po usunięciu pliku.
- Nie dodajemy plików większych niż 10 MB ani pełnego zbioru zdjęć produktów. Zdjęcia publikujemy jako archiwum w Releases.
