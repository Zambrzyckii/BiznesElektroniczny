# Dziennik AI

| Data i autor | Narzędzie i model | Zadanie | Co otrzymano | Co było błędne | Weryfikacja |
|---|---|---|---|---|---|
| 2026-10-25 SuperAkara | Claude (Opus 5.5) | #21 #3 Scraper: klient HTTP (tempo, robots.txt, User-Agent, cache), sitemapy i CI | Klient HTTP (limit tempa, robots.txt, User-Agent, cache, ponawianie), pobieranie sitemap, workflow CI, testy z udawanym serwerem | Pierwsza propozycja używała urllib.robotparser, który nie rozumie * w robots.txt (reguły /*?order= byłyby ignorowane), zamienione na protego. Log zapisywany po odpowiedzi pokazywał odstępy 0,45 s, teraz log w chwili wysłania. Parser sitemap brał też adresy zdjęć (<image:loc>) | Testy bez sieci (robots, tempo, tempo w logu, cache, wznawianie, sitemapy); log z prawdziwego przebiegu: min. odstęp 0,586 s |
