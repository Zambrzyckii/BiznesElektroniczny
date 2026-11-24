"""Testy przygotowania zdjęć. Zdjęcia generujemy w teście (Pillow), bez internetu."""

import io
import logging
import random

import pytest
from PIL import Image

from images import MAX_BYTES, ImageTooSmall, download_all, prepare_image


def zrob_obraz(szer, wys, format="JPEG", szum=False, tryb="RGB"):
    """Wygeneruj obrazek testowy i zwróć jego bajty."""
    if szum:  # szum słabo się kompresuje: najgorszy przypadek dla limitu 300 KB
        losowe = random.Random(0)  # własny generator, nie zmienia globalnego random
        obraz = Image.frombytes("RGB", (szer, wys), losowe.randbytes(szer * wys * 3))
    else:
        obraz = Image.new(tryb, (szer, wys), (200, 120, 50) if tryb == "RGB" else (200, 120, 50, 128))
    bufor = io.BytesIO()
    obraz.save(bufor, format)
    return bufor.getvalue()


def rozmiar(bajty):
    return Image.open(io.BytesIO(bajty)).size


def test_zdjecie_ze_sklepu_zostaje_w_tym_samym_rozmiarze():
    wynik = prepare_image(zrob_obraz(848, 1200))   # typowe zdjęcie large_default ze sklepu
    assert rozmiar(wynik) == (848, 1200)


def test_duze_zdjecie_jest_zmniejszone_do_1600():
    wynik = prepare_image(zrob_obraz(3000, 2000))
    assert rozmiar(wynik) == (1600, 1067)          # proporcje zachowane


def test_trudne_zdjecie_miesci_sie_w_300kb():
    wynik = prepare_image(zrob_obraz(1600, 1600, szum=True))
    assert len(wynik) <= MAX_BYTES == 300_000
    assert 800 <= max(rozmiar(wynik)) <= 1600


def test_zdjecie_tuz_nad_800_px_moze_zejsc_do_800():
    # 850 px * 0,9 < 800, więc ostatnia próba ma być dokładnie 800 px, a nie od razu błąd
    wynik = prepare_image(zrob_obraz(850, 850, szum=True))
    assert len(wynik) <= MAX_BYTES
    assert max(rozmiar(wynik)) in (800, 850)


def test_miniatura_jest_odrzucona():
    with pytest.raises(ImageTooSmall):
        prepare_image(zrob_obraz(370, 524))          # rozmiar home_default ze sklepu


def test_png_z_przezroczystoscia_i_webp_zamieniane_na_jpeg():
    for dane in (zrob_obraz(900, 900, "PNG", tryb="RGBA"), zrob_obraz(900, 900, "WEBP")):
        wynik = prepare_image(dane)
        assert Image.open(io.BytesIO(wynik)).format == "JPEG"


class FakeFetcher:
    def __init__(self):
        self.network_requests = 0

    def get_bytes(self, url):
        self.network_requests += 1
        if "zepsute" in url:
            return b"to nie jest obrazek"
        return zrob_obraz(848, 1200)


PRODUKTY = [
    {"id": 36, "images": ["https://x/1.jpg", "https://x/2.jpg"]},
    {"id": 237, "images": ["https://x/3.jpg", "https://x/zepsute.jpg"]},
]


def test_pobiera_nazywa_i_pomija_zepsute(tmp_path):
    pliki, bledy = download_all(FakeFetcher(), PRODUKTY, tmp_path)
    assert pliki == {
        36: [{"file": "36-1.jpg", "source_url": "https://x/1.jpg"}, {"file": "36-2.jpg", "source_url": "https://x/2.jpg"}],
        237: [{"file": "237-1.jpg", "source_url": "https://x/3.jpg"}],
    }
    assert bledy == 1
    assert (tmp_path / "36-2.jpg").exists()


def test_wznawianie_nie_pobiera_istniejacych(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="scraper")
    download_all(FakeFetcher(), PRODUKTY, tmp_path)
    drugi_raz = FakeFetcher()
    download_all(drugi_raz, PRODUKTY, tmp_path)
    assert drugi_raz.network_requests == 1           # tylko uszkodzone, bo nie zostało zapisane
    assert "3 pominiętych" in caplog.text


def test_produkt_bez_zadnego_zdjecia_jest_w_logu(tmp_path, caplog):
    caplog.set_level(logging.ERROR, logger="scraper")
    pliki, _ = download_all(FakeFetcher(), [{"id": 5, "images": ["https://x/zepsute.jpg"]}], tmp_path)
    assert pliki == {}
    assert "Produkt 5 nie ma żadnego zdjęcia" in caplog.text

