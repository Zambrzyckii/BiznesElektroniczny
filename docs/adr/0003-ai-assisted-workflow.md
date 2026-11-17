# ADR 0003: Praca zespołu z agentami AI

- **Status:** zaakceptowana
- **Data:** 2026-11-17

## Kontekst

Zespół korzysta z trzech różnych narzędzi AI (Claude Code, aplikacja Claude i Antigravity), co widać w `docs/AI_LOG.md`. Bez wspólnych zasad każde z nich zgaduje konwencje repozytorium, a my poprawiamy te same błędy w kolejnych PR-ach.

Zasady przedmiotu się nie zmieniają. Wymaganie W1 każe recenzować każdy PR przez inną osobę (`CONTRIBUTING.md`, sekcja „Recenzje”), wymaganie D6 obejmuje ADR-y i dziennik AI, a wpisy do niego są obowiązkowe (sekcja „Narzędzia AI”). Na obronie trzeba też umieć wyjaśnić kod napisany z pomocą AI. Agent może więc przyspieszyć pracę, ale nie zdejmuje z nas odpowiedzialności za wynik.

Dodatkowo ADR 0002 zakłada, że każda gałąź startuje z aktualnego `main`. To utrudnia zadania, które potrzebują niescalonego jeszcze issue, bo ich PR-y musiałyby czekać na scalenie poprzednika.

## Rozważane opcje

| Opcja | Zalety | Wady |
|---|---|---|
| **A. Wspólny rdzeń `AGENTS.md`, warstwa Claude Code w `.claude/` i ten ADR (wybrana)** | Standardowe i lekkie rozwiązanie. `AGENTS.md` pomaga każdemu narzędziu, a nie tylko jednemu. Proces jest w repozytorium, więc zespół może go przejrzeć i poprawić | Wymaga dodatkowych issues i recenzji przez zespół. Trzeba pilnować, żeby `AGENTS.md` pozostał krótki |
| B. Framework oparty na specyfikacjach (Spec Kit lub BMAD) | Rozpoznawalna nazwa i pełny zestaw artefaktów | Powiela nasze issues, dodaje do repozytorium wiele plików, z których zespół nie skorzysta, i ukrywa treść promptów |
| C. Prywatna warstwa w katalogu domowym jednej osoby, w repozytorium tylko `AGENTS.md` | Najszybsza w uruchomieniu i bez dyskusji w zespole | Proces nigdy nie trafia do repozytorium, więc reszta zespołu go nie widzi, nie recenzuje i nie może go obronić |

Nie używamy wektorowego RAG. Agenci szukają w kodzie przez grep i czytanie plików, a repozytorium jest małe, więc indeks wektorowy dodałby infrastrukturę bez wyraźnego zysku.

## Decyzja

Przyjmujemy opcję A.

1. **Układ plików.**
   - `AGENTS.md` zawiera zasady dla każdego narzędzia AI.
   - `CLAUDE.md` zaczyna się od `@AGENTS.md` i dodaje tylko reguły specyficzne dla Claude Code.
   - `.claude/agents/` zawiera czterech agentów, a `.claude/skills/` dwa skille.
   - `.claude/settings.json` blokuje `Read` dla plików `.env` (`./.env`, `./**/.env` i `//**/.env`, czyli także ścieżki bezwzględne). Plik `.env.example` pozostaje czytelny.
   - `.gitignore` pomija `.claude/settings.local.json`, `CLAUDE.local.md` i `.claude/worktrees/`.
2. **Język.** `AGENTS.md`, `CLAUDE.md`, prompty agentów i skilli są po angielsku, bo to konfiguracja agentów. ADR-y, `CONTRIBUTING.md` i `docs/AI_LOG.md` są po polsku, zgodnie z `CONTRIBUTING.md`.
3. **Agenci.**
   - `planner` (model `opus`, wysiłek `xhigh`) czyta issue i kod, niczego nie zmienia i zwraca plan.
   - `implementer` (`sonnet`, `high`) wykonuje jeden zatwierdzony plan na wskazanej gałęzi. Nie uruchamia `docker compose up`.
   - `reviewer` (`opus`, `high`) ma tylko narzędzia Read, Grep i Glob. Czyta zmianę od zera, bez wniosków autora.
   - `docs-writer` (`sonnet`, `high`) pisze po polsku dokumentację, opis PR i wpis do dziennika AI.
4. **Skille.**
   - `issue-to-pr` jest uruchamiany wyłącznie ręcznie, bo ma skutki uboczne. Prowadzi od issue do otwartego PR przez planistę, bramkę decyzyjną, implementera, `verify-stack`, recenzenta i autora dokumentacji.
   - Worktree tworzy jawnym `git worktree add` z podanej gałęzi bazowej. Nie polega na domyślnej izolacji agentów, która mogłaby wystartować z niewłaściwego commita.
   - Poprawki po weryfikacji i recenzji dzielą limit dwóch rund. Po bramce skill działa do końca, wypycha gałąź i otwiera PR z etykietą `ai-assisted`. PR jest gotowy do recenzji, a szkicem pozostaje dla gałęzi piętrowych i gdy `verify-stack` zwrócił `SKIPPED` dla zmian w `deploy/` lub `shop/`. Z flagą `lokalnie` skill zatrzymuje się przed wypchnięciem.
   - `verify-stack` uruchamia stos Docker tego repozytorium.
   - `ready-pr` jest uruchamiany ręcznie po scaleniu rodzica. Przenosi gałąź na `main` według punktu 7, oznacza PR jako gotowy, czeka do około 10 minut na CI i bota recenzującego i w jednej rundzie poprawia ich trafne uwagi. Nie odpowiada na komentarze i nie zleca ponownej recenzji. Część z czekaniem wykonuje też `issue-to-pr` dla PR-a otwartego jako gotowy.
5. **Bramka decyzyjna.** Brief planisty kończy się sekcją `## Open decisions`. Gdy brief ma otwarte decyzje albo issue nie ma przypisanej osoby, `issue-to-pr` zbiera je w jednej wiadomości, a decyzję podejmuje użytkownik. Bez pytań trasa idzie dalej bez zatrzymania. Decyzje wiążące resztę zespołu trafiają do opisu PR.
6. **Docker.** W sesjach Claude Code jednocześnie działa jeden stos tego repozytorium, uruchamiany przez `verify-stack` pod nazwą `COMPOSE_PROJECT_NAME=be-verify` z katalogu `deploy/`. Zasada nie dotyczy zespołu, który uruchamia `docker compose` samodzielnie. Skill odmawia startu, gdy `MemAvailable` jest poniżej 3 GiB albo działa już projekt tego repozytorium, czyli o nazwie zaczynającej się od `be-` albo o nazwie `deploy`. Innych projektów compose nie dotyka, a `down -v` wykonuje tylko po własnym `up`. Równoległe sesje czekają na swoją kolej przy blokadzie `/tmp/be-verify.lock`, a `issue-to-pr` kopiuje do nowego worktree plik `deploy/.env` bez czytania jego treści.
7. **Gałęzie piętrowe (uzupełnienie ADR 0002).**
   - Gałąź, która potrzebuje niescalonego issue, może wystartować z gałęzi tego issue.
   - Jej PR kieruje się do gałęzi rodzica i jest szkicem do czasu scalenia rodzica.
   - Po scaleniu rodzica gałąź jest przenoszona na `main` przez `git rebase --onto`, wypychana przez `git push --force-with-lease`, cel PR-a zmienia się na `main` i dopiero wtedy PR przechodzi w Ready for review.
   - ADR 0002 pozostaje bez zmian. Ta reguła dodaje wyjątek od jego punktu 4 i jest zapisana w `CONTRIBUTING.md`.
8. **Prostota kodu.** Agenci piszą najprostszy czytelny kod, nawet kosztem drobnej wydajności, i nie dodają abstrakcji, opcji ani warstw, których zadanie nie wymaga. Teksty pisane dla ludzi są krótkie i proste.

## Konsekwencje

### Zalety
- Każde narzędzie AI w zespole czyta te same zasady z `AGENTS.md`, więc mniej poprawek konwencji w recenzjach.
- Proces pracy z agentami jest w repozytorium, więc zespół może go przejrzeć, zakwestionować i wyjaśnić na obronie.
- Niezależny recenzent i bramka decyzyjna ograniczają ryzyko, że autor lub agent zatwierdzi własne założenia.
- Weryfikacja Dockera jest szeregowa i oddzielona od lokalnego środowiska deweloperskiego, więc nie startuje obok innego stosu tego repozytorium ani przy mniej niż 3 GiB wolnej pamięci i nie kasuje cudzych wolumenów.
- Gałęzie piętrowe pozwalają zacząć kolejne zadanie, zanim poprzednie zostanie scalone.

### Koszty i ograniczenia
- `AGENTS.md` trzeba utrzymywać krótkim i aktualnym. Plik, który się rozrasta albo rozjeżdża z kodem, szkodzi bardziej niż jego brak.
- Zespół dostaje dodatkowe PR-y do recenzji (warstwa agentów, a potem kolejne etapy), więc rośnie obciążenie recenzentów.
- Agentów i skille trzeba aktualizować razem z repozytorium, na przykład gdy zmieni się układ usług w `deploy/compose.yaml`.
- Katalog `.claude/` czyta tylko Claude Code. Pozostałe narzędzia korzystają wyłącznie z `AGENTS.md`.
- Blokada odczytu `.env` w `.claude/settings.json` nie zatrzymuje poleceń powłoki. Przed nimi chroni zasada „Never” w `AGENTS.md`. W pierwszej wersji nie dodajemy hooków i wrócimy do tematu dopiero po realnym naruszeniu.
- Gałęzie piętrowe wymagają dodatkowego kroku po scaleniu rodzica i uwagi przy zmianie celu PR-a.
- Kolejne elementy procesu (bot recenzujący PR-y, skill do nauki i realizacja zaplanowanych issues) opiszemy w osobnych issues i PR-ach.
