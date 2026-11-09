"""Testy fetchera bez sieci: FakeSession rejestruje adresy, czasy i nagłówki zapytań."""

import logging
import time

import pytest

from fetcher import BlockedByRobots, Fetcher

# Fragment prawdziwego robots.txt z dobrakaloria.pl
ROBOTS = """
User-agent: *
Disallow: /*?order=
Disallow: /*&order=
Disallow: /*?n=
Disallow: /koszyk
Disallow: /szukaj
"""


class FakeResponse:
    def __init__(self, tekst, status_code=200):
        self.content = tekst.encode("utf-8")
        self.status_code = status_code


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.calls = []  # lista (adres, czas, User-Agent)

    def get(self, url, timeout):
        self.calls.append((url, time.monotonic(), self.headers.get("User-Agent")))
        return FakeResponse(f"<html>strona {url} zażółć</html>")


@pytest.fixture
def fetcher(tmp_path):
    return Fetcher(ROBOTS, cache_dir=tmp_path, min_interval=0.2, session=FakeSession())


def test_robots_pozwala_na_kolejne_strony(fetcher):
    fetcher.get("https://dobrakaloria.pl/2-wszystkie-produkty?page=2")
    assert fetcher.network_requests == 1


@pytest.mark.parametrize("zabroniony", [
    "https://dobrakaloria.pl/2-wszystkie-produkty?order=product.price.asc",
    "https://dobrakaloria.pl/2-wszystkie-produkty?page=2&order=product.name.asc",
    "https://dobrakaloria.pl/2-wszystkie-produkty?n=1000",
    "https://dobrakaloria.pl/koszyk",
])
def test_robots_blokuje_zabronione(fetcher, zabroniony):
    with pytest.raises(BlockedByRobots):
        fetcher.get(zabroniony)
    assert fetcher.network_requests == 0


def test_wysyla_user_agent(fetcher):
    fetcher.get("https://dobrakaloria.pl/32-batony-klasyczne")
    _, _, user_agent = fetcher.session.calls[0]
    assert user_agent.startswith("PG-Student-Scraper")


def test_tempo_zapytan(fetcher):
    for i in range(3):
        fetcher.get(f"https://dobrakaloria.pl/{i}-kategoria")
    czasy = [czas for _, czas, _ in fetcher.session.calls]
    odstepy = [b - a for a, b in zip(czasy, czasy[1:])]
    assert all(o >= 0.17 for o in odstepy), odstepy  # margines na rozdzielczość zegara (Windows)


def test_log_pokazuje_prawdziwe_tempo(fetcher, caplog):
    # znaczniki czasu w logu muszą odzwierciedlać faktyczne tempo
    caplog.set_level(logging.INFO, logger="scraper")
    for i in range(3):
        fetcher.get(f"https://dobrakaloria.pl/{i}-kategoria")
    czasy = [r.created for r in caplog.records if r.getMessage().startswith("GET ")]
    assert len(czasy) == 3
    odstepy = [b - a for a, b in zip(czasy, czasy[1:])]
    assert all(o >= 0.17 for o in odstepy), odstepy  # margines na rozdzielczość zegara (Windows)


def test_cache_nie_pobiera_drugi_raz(fetcher):
    url = "https://dobrakaloria.pl/32-batony-klasyczne"
    pierwszy = fetcher.get(url)
    drugi = fetcher.get(url)
    assert pierwszy == drugi
    assert fetcher.network_requests == 1
    assert fetcher.cache_hits == 1


def test_wznawianie_po_przerwaniu(tmp_path):
    url = "https://dobrakaloria.pl/32-batony-klasyczne"
    Fetcher(ROBOTS, tmp_path, session=FakeSession()).get(url)

    # nowy Fetcher z tym samym cache = ponowne uruchomienie programu
    po_restarcie = Fetcher(ROBOTS, tmp_path, session=FakeSession())
    po_restarcie.get(url)
    assert po_restarcie.network_requests == 0
    assert po_restarcie.cache_hits == 1


def test_polskie_znaki_z_sieci(fetcher):
    assert "zażółć" in fetcher.get("https://dobrakaloria.pl/1-x")
