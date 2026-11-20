# ADR 0007: Proxy HTTPS z certyfikatem self-signed

- **Status:** zaakceptowana
- **Data:** 2026-11-17

## Kontekst

Wymaganie W3 [K] mówi, że ruch idzie wyłącznie po HTTPS z samodzielnie wygenerowanym certyfikatem, a HTTP jest przekierowywane kodem 301. Prowadzący sprawdzi to na odbiorze, wchodząc na sklep przez HTTP.

- ADR 0003 zostawił HTTPS na #13 i wskazał, że domena sklepu jest zapisana w bazie podczas instalacji.
- Za proxy, które kończy TLS, sklep musi wiedzieć, że żądanie przyszło po HTTPS. Inaczej przekierowuje na HTTPS w pętli.
- PrestaShop 8.2.8 w `admin-dev/index.php` wywołuje `Request::setTrustedProxies([], ...)`, więc strony panelu oparte na Symfony nie ufają nagłówkom proxy.
- Strony front office sprawdzają HTTPS w `Tools::usingSecureMode()`, które korzysta z `HTTP_X_FORWARDED_PROTO`.

## Rozważane opcje

### Gdzie kończy się TLS

| Opcja | Zalety | Wady |
|---|---|---|
| **nginx w osobnym kontenerze (wybrana)** | Obraz sklepu zostaje bez zmian. Etap 2 ma osobny punkt wejścia przed sklepem. Przekierowanie 301 i TLS są w jednym pliku. | Dodatkowy kontener i plik konfiguracji. Sklep musi dowiedzieć się o HTTPS z nagłówka. |
| Caddy | Krótka konfiguracja. | Certyfikat podpisuje lokalne CA Caddy, więc nie jest to certyfikat self-signed. Domyślne przekierowanie ma kod 308, a nie 301. |
| HTTPS w Apache w kontenerze sklepu | Brak dodatkowego kontenera i nagłówka proxy. | TLS trafia do obrazu sklepu budowanego w #12. Etap 2 traci osobny punkt wejścia. |

### Skąd bierze się certyfikat

| Opcja | Zalety | Wady |
|---|---|---|
| **`openssl` w poleceniu usługi `proxy`, zapis do wolumenu (wybrana)** | Jedna komenda startu. Certyfikat powstaje tylko wtedy, gdy w wolumenie nie ma `localhost.crt`, więc przeżywa restarty. | Polecenie w `compose.yaml` jest dłuższe. `down -v` usuwa certyfikat. |
| Osobna usługa jednorazowa | Wyraźny podział odpowiedzialności. | Dodatkowa usługa i warunek `service_completed_successfully` w `depends_on`. |
| Skrypt uruchamiany ręcznie | Pełna kontrola nad certyfikatem. | Dodatkowy krok przed startem, wbrew zasadzie jednej komendy z W3 [K]. |

### Porty na hoście

| Opcja | Zalety | Wady |
|---|---|---|
| **Stałe 80 i 443 (wybrana)** | `curl -I http://localhost/` działa dosłownie tak, jak wymaga kryterium issue. Adres sklepu w bazie nie ma portu. | Zajęte porty 80 lub 443 blokują start. |
| Porty z `deploy/.env` | Każdy może wybrać wolne porty. | Port HTTPS staje się częścią domeny sklepu w bazie, więc późniejsza zmiana wymaga `down -v`. |
| 8080 i 8443 | Rzadziej zajęte. | Kryterium z `curl -I http://localhost/` nie jest spełnione dosłownie. |

### Jak sklep dowiaduje się o HTTPS

| Opcja | Zalety | Wady |
|---|---|---|
| **`X-Forwarded-Proto` i `SetEnvIf` w Apache ustawiające `HTTPS=on` (wybrana)** | Działa w front office i w panelu, bo `HTTPS=on` widzi też Symfony, który nie ufa nagłówkom. | Dodatkowy plik `deploy/shop-https.conf` zamontowany do Apache. |
| Sam nagłówek `X-Forwarded-Proto` | Brak dodatkowego pliku. Front office działa. | Strony panelu oparte na Symfony budują adresy `http://`. |

## Decyzja

Dodajemy usługę `proxy` do `deploy/compose.yaml`, a sklep traci port na hoście.

| Usługa | Obraz | Wolumen | Port na hoście | Healthcheck |
|---|---|---|---|---|
| `db` | `mariadb:10.11` | `db-data:/var/lib/mysql` | brak | `healthcheck.sh --connect --innodb_initialized` |
| `shop` | `prestashop/prestashop:8.2.8-8.1-apache` | `shop-data:/var/www/html` | brak | brak katalogu `install` i odpowiedź serwera WWW |
| `proxy` | `nginx:1.30.6` | `proxy-certs:/etc/nginx/certs` | `80:80` i `443:443` | brak |

Przyjmujemy następujące zasady.

- Port 80 odpowiada kodem 301 na `https://$host$request_uri` dla każdego adresu (`deploy/proxy.conf`).
- TLS kończy się w nginx na porcie 443. Żądania idą do `http://shop` z nagłówkami `Host` i `X-Forwarded-Proto: https`.
- Certyfikat tworzy `openssl` w poleceniu usługi `proxy` przy pierwszym starcie. Ma `CN=localhost`, `subjectAltName=DNS:localhost` i ważność 365 dni. Klucz i certyfikat leżą w wolumenie `proxy-certs`, a nie w repozytorium.
- Apache w sklepie czyta `deploy/shop-https.conf` zamontowany tylko do odczytu. Reguła `SetEnvIf X-Forwarded-Proto "^https$" HTTPS=on` ustawia `HTTPS=on` dla żądań z proxy.
- Sklep dostaje `PS_DOMAIN: localhost` i `PS_ENABLE_SSL: 1`. Ta zmienna włącza przy instalacji `PS_SSL_ENABLED` i `PS_SSL_ENABLED_EVERYWHERE`, co jest potrzebne, żeby uniknąć pętli przekierowań.
- Usługa `proxy` startuje, gdy `shop` jest zdrowy (`depends_on` z `condition: service_healthy` i `restart: true`).

## Konsekwencje

- Sklep zainstalowany przed tą zmianą ma w bazie `localhost:8080` i wyłączone SSL, bo `PS_DOMAIN` i `PS_ENABLE_SSL` działają tylko przy pierwszej instalacji. Wymaga `down -v` i ponownego startu.
- Przeglądarka ostrzega o certyfikacie self-signed, dopóki użytkownik go nie zaakceptuje.
- Porty 80 i 443 muszą być wolne na komputerze, bo są stałe.
- Certyfikat jest ważny 365 dni. Po usunięciu wolumenu `proxy-certs` (np. przez `down -v`) powstaje nowy.
- Przez proxy przechodzą pliki do 20 MB (`client_max_body_size 20m`).
- `depends_on.restart: true` wymaga Docker Compose 2.17 lub nowszego. Przy ponownym utworzeniu usługi `shop` Compose restartuje też nginx.
- Etap 2 może użyć proxy jako osobnego punktu wejścia przed sklepem, bez zmian w obrazie sklepu.
