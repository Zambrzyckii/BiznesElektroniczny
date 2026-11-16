# ADR 0002: Przepływ pracy z repozytorium i scalanie zmian

- **Status:** zaakceptowana
- **Data:** 2026-11-15

## Kontekst

Wymaganie `W1 [K]` narzuca, aby wszystkie zmiany na gałęzi `main` (po początkowym szkielecie repozytorium) trafiały wyłącznie przez zatwierdzone pull requesty recenzowane przez inną osobę z zespołu, bez bezpośrednich commitów na `main`. Dodatkowo w 4-osobowym zespole pracującym równolegle nad wieloma zadaniami historia `main` musi pozwalać łatwo powiązać każdą zmianę z odpowiednim issue i PR-em, a także wycofać pojedyncze zadanie w razie regresji.

Zasady praktyczne opisaliśmy już w pliku `CONTRIBUTING.md`, natomiast w tym dokumencie formalizujemy wybrane ustawienia repozytorium na Githubie i model pracy z gałęziami. 

Numer `ADR 0002` wynika z faktu, że w katalogu istnieje już wcześniej scalony `0001-biblioteka-scrapera.md`.

## Rozważane opcje

### 1. Strategia scalania pull requestów do `main`

| Opcja | Zalety | Wady |
|---|---|---|
| **Squash and merge (wybrana)** | Jeden commit na jeden PR w historii `main`; czytelny format `<Tytuł PR> (#N)`; łatwy `git revert` całego zadania; autorzy mogą robić robocze commity na gałęzi | Znikają pojedyncze, pośrednie commity z gałęzi roboczej na `main` |
| Merge commit | Zachowuje pełną historię pośrednich commitów z gałęzi | Zaśmieca `main` roboczymi commitami (np. „fix”) i dodatkowymi commitami scalającymi bez spójnego numeru PR-a |
| Rebase and merge | Liniowa historia bez commitów scalających; zachowuje pojedyncze commity | Wymaga ręcznego czyszczenia i poprawiania komunikatów commitów przed scaleniem; pojedyncze zadanie nadal rozpada się na wiele commitów przy wycofywaniu zmian |

### 2. Model gałęzi

| Opcja | Zalety | Wady |
|---|---|---|
| **Gałęzie funkcyjne bezpośrednio do `main` (wybrana)** | Prosty przepływ (`<issue_number>-short-description` → PR → `main`); brak rozjazdów między gałęzią integracyjną a `main`; w etapie 1 `main` jest jedynym punktem odniesienia | Wymaga, aby każdy PR wchodził w stanie działającym i przechodził CI |
| Dodatkowa gałąź integracyjna `dev` | Pozwala grupować wiele zadań przed wejściem na `main` | Zbędny narzut w 4-osobowym projekcie; konflikty przy okresowym scalaniu `dev` → `main` oraz gubienie bezpośredniego powiązania `1 issue = 1 PR na main` |

## Decyzja

Przyjmujemy następujący workflow oraz odpowiadającą mu konfigurację repozytorium na GitHubie:

1. **Wyłączne scalanie przez `Squash and merge`** — przy scalaniu tytuł PR-a staje się tytułem jedynego commita trafiającego na `main` z dopiskiem `(#N)`.
2. **Ochrona gałęzi `main`** (bez wyjątku dla administratora) — bezpośrednie wypychanie zmian (`push`) i nadpisywanie historii (`force push`) są zablokowane dla wszystkich członków zespołu. Wymagana jest co najmniej jedna akceptacja recenzenta, który nie jest autorem PR.
3. **Automatyczne usuwanie gałęzi** — po scaleniu PR-a jego gałąź źródłowa jest automatycznie usuwana na GitHubie.
4. **Praca bezpośrednio na gałęziach `<issue_number>-short-description` z `main`** — bez pośredniej gałęzi `dev`.

## Konsekwencje

### Zalety
- Historia `main` jest liniowa i stanowi bezpośredni dziennik zrealizowanych zadań (`Tytuł PR (#N)`), co ułatwia przegląd postępów, przygotowanie do obrony i ewentualne wycofanie pojedynczego zadania jednym `git revert`.
- Zespół nie musi ręcznie poprawiać roboczych commitów (`rebase -i`) na gałęziach funkcyjnych.
- Ochrona `main` gwarantuje recenzję każdego PR.
- Automatyczne usuwanie gałęzi utrzymuje porządek na zdalnym repozytorium mimo kilkudziesięciu krótkich gałęzi z issues.

### Koszty i ograniczenia
- Nawet drobne poprawki w dokumentacji wymagają od nas pełnej ścieżki: gałąź → PR → recenzja innej osoby.
- Po scaleniu tracimy na `main` granularność pośrednich commitów z gałęzi, co przy bardzo dużych PR-ach utrudniałoby szukanie przyczyny błędu. Wymusza to pilnowanie zasady małych, jednozadaniowych PR-ów.
- Tytuł PR-a musimy dopracować przed kliknięciem `Squash and merge`, ponieważ po scaleniu zostaje w historii `main` na stałe.
- Okresowo czyścimy nieaktualne gałęzie (`git fetch --prune`).
