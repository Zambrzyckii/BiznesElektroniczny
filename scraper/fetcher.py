"""Pobieranie stron i plików ze sklepu źródłowego (jedyny moduł korzystający z sieci).

- tempo: co najmniej MIN_INTERVAL s między zapytaniami
- robots.txt: przez protego, które obsługuje reguły z "*" (urllib.robotparser nie)
- własny User-Agent
- cache na dysku: po przerwaniu i ponownym uruchomieniu nic nie jest pobierane drugi raz
"""

import hashlib
import logging
import time
from pathlib import Path

import requests
from protego import Protego

USER_AGENT = "PG-Student-Scraper/1.0 (projekt dydaktyczny, bez celow komercyjnych)"
MIN_INTERVAL = 0.6  # s, czyli ok. 1.7 zapytania/s (limit: 2/s)

log = logging.getLogger("scraper")


class BlockedByRobots(Exception):
    """Adres jest zabroniony w robots.txt."""


class Fetcher:
    def __init__(self, robots_txt, cache_dir, min_interval=MIN_INTERVAL,
                 session=None, user_agent=USER_AGENT):
        self.robots = Protego.parse(robots_txt)
        self.cache_dir = Path(cache_dir)
        self.min_interval = min_interval
        self.user_agent = user_agent
        # session można podmienić w testach
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self._last_request = None
        self.network_requests = 0   # zapytania faktycznie wysłane
        self.cache_hits = 0         # odczyty z cache (pominięte pobrania po wznowieniu)

    @classmethod
    def for_site(cls, base_url, cache_dir, **kwargs):
        """Fetcher dla sklepu z jego aktualnym robots.txt."""
        session = requests.Session()
        session.headers["User-Agent"] = kwargs.get("user_agent", USER_AGENT)
        odp = session.get(base_url.rstrip("/") + "/robots.txt", timeout=20)
        odp.raise_for_status()
        log.info("Pobrano robots.txt (%d znaków)", len(odp.text))
        fetcher = cls(odp.text, cache_dir, session=session, **kwargs)
        fetcher._last_request = time.monotonic()  # pobranie robots.txt liczy się do tempa
        return fetcher

    def get(self, url):
        """HTML strony (z cache albo z sieci)."""
        return self._get(url, sufiks=".html").decode("utf-8", errors="replace")

    @property
    def sitemaps(self):
        """Adresy sitemap z linii "Sitemap:" w robots.txt."""
        return list(self.robots.sitemaps)

    def get_bytes(self, url):
        """Surowe bajty, np. zdjęcia (z cache albo z sieci)."""
        return self._get(url, sufiks=".bin")

    def _get(self, url, sufiks):
        plik = self._cache_path(url, sufiks)

        if plik.exists():
            self.cache_hits += 1
            return plik.read_bytes()

        if not self.robots.can_fetch(url, self.user_agent):
            raise BlockedByRobots(url)

        tresc = self._download(url)

        # zapis przez plik tymczasowy: przerwanie w trakcie nie zostawi uciętego pliku
        plik.parent.mkdir(parents=True, exist_ok=True)
        tmp = plik.with_suffix(".tmp")
        tmp.write_bytes(tresc)
        tmp.replace(plik)
        return tresc

    def _download(self, url, proby=3):
        for proba in range(1, proby + 1):
            self._wait_for_turn()
            self.network_requests += 1
            # Log w chwili wysłania, żeby znaczniki czasu odzwierciedlały faktyczne
            # odstępy między zapytaniami (log po odpowiedzi zaniżałby je o czas odpowiedzi).
            log.info("GET %s", url)
            try:
                odp = self.session.get(url, timeout=20)
            except requests.RequestException as e:
                log.warning("  błąd sieci (%s), próba %d/%d", e, proba, proby)
            else:
                if odp.status_code == 200:
                    return odp.content
                log.warning("  odpowiedź %d, próba %d/%d", odp.status_code, proba, proby)
                if odp.status_code < 500 and odp.status_code != 429:
                    break  # błędy klienta (404, 403...) nie są przejściowe
            time.sleep(2 * proba)
        raise RuntimeError(f"Nie udało się pobrać {url}")

    def _wait_for_turn(self):
        """Czekaj, aż od poprzedniego zapytania minie min_interval."""
        if self._last_request is not None:
            minelo = time.monotonic() - self._last_request
            if minelo < self.min_interval:
                time.sleep(self.min_interval - minelo)
        self._last_request = time.monotonic()

    def _cache_path(self, url, sufiks):
        # SHA-1 adresu jako nazwa pliku (URL zawiera znaki niedozwolone w nazwach plików)
        nazwa = hashlib.sha1(url.encode("utf-8")).hexdigest()
        return self.cache_dir / (nazwa + sufiks)
