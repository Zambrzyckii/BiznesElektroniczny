# ADR 0004: Automatyczna wstępna recenzja PR-ów przez AI

- **Status:** zaakceptowana
- **Data:** 2026-11-17

## Kontekst

Wąskim gardłem jest czas do pierwszej recenzji, bo recenzent ma na odpowiedź 48 godzin (`CONTRIBUTING.md:43`). Zasady przedmiotu się nie zmieniają. Każdy PR nadal wymaga recenzji osoby z zespołu z co najmniej jednym merytorycznym komentarzem (`CONTRIBUTING.md:41-44`), a prowadzący liczy `reviewed-by:` ręcznie. Issue powołuje się na W1 i D5.

Zespół używa trzech narzędzi AI, a recenzje piszemy po polsku. Bot ma więc skrócić czas do pierwszej informacji zwrotnej, a nie zastąpić człowieka. Uzupełnia ADR 0003, który opisuje agentów używanych lokalnie.

## Rozważane opcje

| Opcja | Zalety | Wady |
|---|---|---|
| **A. Własny workflow z `claude-code-action` i polskim promptem (wybrana)** | Pełna kontrola nad promptem, językiem i narzędziami bota. Działa na zwykłym koncie API | Prompt i workflow trzeba utrzymywać samemu |
| B. Oficjalna wtyczka `code-review` w workflow | Gotowy prompt | Pisze po angielsku i pomija PR-y, które mają już komentarz Claude, więc ponowna recenzja przez `@claude` by nie działała |
| C. Zarządzany Code Review od Anthropic | Brak własnego workflow | Dostępny tylko w planach Team i Enterprise, których nie mamy |
| D. Brak bota | Brak kosztu i brak nowych zasad | Pierwsza informacja zwrotna nadal zależy wyłącznie od czasu recenzenta |

## Decyzja

Przyjmujemy opcję A. Workflow jest w `.github/workflows/claude-review.yml`.

1. **Wyzwalacze.** Bot recenzuje PR po `opened` i `ready_for_review`, a szkicu automatycznie nie recenzuje. Komentarz z `@claude` od osoby z rolą OWNER, MEMBER lub COLLABORATOR uruchamia ponowną recenzję, także szkicu, i zużywa kredyt. Komentarze w rozmowie PR-a są w GitHubie komentarzami issue, więc potrzebne jest zdarzenie `issue_comment`, które GitHub uruchamia tylko z pliku workflow w gałęzi domyślnej. Dlatego `@claude` działa dopiero po scaleniu workflow do `main`.
2. **Model.** `claude-opus-5-5`.
3. **Tożsamość.** Komentarze pisze `claude[bot]` przez aplikację Claude GitHub App. Workflow nie przekazuje `github_token`.
4. **Tylko komentarze.** Token aplikacji sam potrafi zatwierdzić PR, więc blokują to reguły narzędzi. Bot działa z `--permission-mode default`, ma krótką listę dozwolonych narzędzi (odczyt, `gh pr view`, `gh pr diff`, `gh issue view`, `gh pr comment` i komentarz inline) oraz listę zabronionych (`gh pr review`, `gh api`, `git push`, `git commit`, `Agent`, `Skill`).
5. **Prompt.** Jest po polsku i ma tę samą kalibrację co agent `reviewer` z ADR 0003. Sprawdza kryteria akceptacji issue, granice z `AGENTS.md` i poprawność, a zbędną złożoność zgłasza tylko z prostszą wersją w jednym zdaniu. Pomija formatowanie, gust nazewniczy i pochwały. Daje najwyżej 5 komentarzy inline i jedno podsumowanie, a treść PR i komentarzy traktuje jako dane.
6. **Finansowanie.** Sekret `ANTHROPIC_API_KEY` z kredytu w Console bez automatycznego doładowania. Wyczerpanie kredytu jest limitem wydatków.
7. **Ograniczenia.** Bez `pull_request_target` i bez PR-ów z forków. Na jeden PR przypada jedna kolejka (`concurrency`), a każdy przebieg ma `timeout-minutes: 15` i `--max-turns 30`.
8. **Etykieta i dziennik AI.** Poprawki po komentarzach bota same w sobie nie wymagają etykiety `ai-assisted` ani wpisu w `docs/AI_LOG.md`. Komentarz bota nie jest recenzją według `CONTRIBUTING.md`.

## Konsekwencje

### Zalety
- Pierwsza informacja zwrotna przychodzi w kilkanaście minut, a osoby z zespołu mogą skupić się na decyzjach.

### Koszty i ograniczenia
- Koszt jednej recenzji poznamy dopiero po zmierzeniu pierwszych trzech.
- PR, który dodaje workflow, i każdy PR, który go zmienia, nie dostaje recenzji bota, bo akcja pomija przebieg, gdy plik workflow różni się od tego w gałęzi domyślnej.
- PR piętrowy, który nadal wskazuje gałąź rodzica, jest szkicem do czasu scalenia rodzica, a recenzja automatyczna pomija szkice. Dostaje ją po zmianie celu na `main` i przejściu w Ready for review. Komentarz `@claude` działa już na takim szkicu.
- Bot czyta `AGENTS.md` z gałęzi bazowej, więc zmiana tego pliku trafia do bota dopiero po scaleniu.
- Aplikacja Claude GitHub App prosi o szeroki zestaw uprawnień.
- Każdy z prawem zapisu może użyć sekretu w zmianie workflow we własnym PR-ze, a szkodę ogranicza limit kredytu.
- Reguła `Bash(gh pr comment:*)` nie jest przypięta do numeru PR-a, więc tekst wstrzyknięty do PR-a zespołu mógłby skłonić bota do komentarza pod innym PR-em lub issue. Bot nadal może tylko komentować, PR-y z forków są odrzucane, a zespół akceptuje to ryzyko.
- Gdy kredyt się skończy, zadanie kończy się błędem. Nie może to blokować scalania, więc nie ustawiamy go jako wymaganego sprawdzenia. Zasada o pipeline zakończonym sukcesem z `CONTRIBUTING.md` dotyczy CI scrapera, a nie zadania Claude Review.
- Wstrzyknięcie promptu przez treść PR-a ogranicza lista narzędzi, która pozwala tylko czytać i komentować.
- **Założenie sprawdzane w teście na żywo.** GitHub pokazuje komentarze inline jako recenzję `claude[bot]` w stanie Commented, która nie jest ani akceptacją, ani żądaniem zmian i nie zmienia niczyjej liczby `reviewed-by:`.
