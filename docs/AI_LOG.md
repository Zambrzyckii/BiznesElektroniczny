# Dziennik AI

Dziennik prowadzimy w formacie z regulaminu przedmiotu. Wpis dodaje osoba, która korzystała z narzędzia AI, w tym samym PR-ze co kod. Każdy z nas dodaje w etapie co najmniej 2 wpisy.

| Data i autor | Narzędzie i model | Zadanie | Co otrzymano | Co było błędne | Weryfikacja |
|---|---|---|---|---|---|
| 2026-10-22, Bartosz Zambrzycki (@Zambrzyckii) | Claude Code, Claude Opus 5.5 | Issues #1-#40, rozpisanie wymagań etapu 1 na zadania | 40 issues z celem, zakresem, kryteriami akceptacji i zależnościami oraz skrypt, który utworzył je przez `gh` | Cztery tytuły miały więcej niż 8 słów. Robocze oznaczenia zadań D1-D10 myliły się z kodami wymagań D1-D6, więc odwołania zamieniono na numery issues. Skrypt miał błąd w wyrażeniu regularnym, który wyłapał tryb sprawdzający przed utworzeniem czegokolwiek. | Przejrzałem wszystkie 40 issues. Skrypt sprawdził liczbę issues, długość tytułów i odwołania, a po utworzeniu wszystkie issues odczytano z API. |
| 2026-10-22, Bartosz Zambrzycki (@Zambrzyckii) | Claude Code, Claude Opus 5.5 | #1, README, CONTRIBUTING, szablony PR i issue oraz ten dziennik | Treść dokumentów wygenerowana na podstawie mojej propozycji, jak mają wyglądać zasady | Zasada, że recenzentem musi być osoba z najmniejszą liczbą recenzji. Wymuszałaby czekanie na jedną osobę, więc ją usunąłem. | Po moim przeglądzie i drobnych poprawkach zaakceptowałem wynik. Fakty o działaniu GitHuba sprawdzono w jego dokumentacji. |
| 2026-10-31, @SuperAkara | Claude (aplikacja Claude), Claude Opus 5.5 | #21 Add scraper skeleton with rate limit and robots.txt | Klient HTTP (limit tempa, robots.txt, User-Agent, cache, ponawianie), pobieranie sitemap, testy z udawanym serwerem | Pierwsza propozycja używała urllib.robotparser, który nie rozumie * w robots.txt (reguły /*?order= byłyby ignorowane), zamienione na protego. Log zapisywany po odpowiedzi pokazywał odstępy 0,45 s, przeniesiony na chwilę wysłania. Parser sitemap brał też adresy zdjęć (<image:loc>) | Testy bez sieci (robots, tempo, tempo w logu, cache, sitemapy); przebieg na sklepie: 137 produktów i 53 kategorie z sitemap, min. odstęp 0,586 s |

## Refleksja zespołu

Refleksję dopiszemy pod koniec etapu 1 w issue [#10](https://github.com/Zambrzyckii/BiznesElektroniczny/issues/10). Opisze, gdzie AI realnie przyspieszyło pracę, gdzie wprowadziło nas w błąd i czego musieliśmy nauczyć się sami.
