"""Zdjęcia produktów: pobranie pełnej rozdzielczości i skalowanie do limitów.

Uruchomienie po main.py, w folderze scraper/:  python images.py

- dłuższy bok 800-1600 px, JPEG <= 300 kB (300 000 B)
- images/<id>-<nr>.jpg, numeracja wg galerii sklepu (1 = zdjęcie główne)
- scraper-results/images.json: plik lokalny i adres źródłowy każdego zdjęcia
- zdjęcia large_default (848x1200) to największy rozmiar, jaki udostępnia sklep
Archiwum i przykłady tworzy archive.py (#27).
"""

import io
import json
import logging
from pathlib import Path

from PIL import Image

import config
from fetcher import Fetcher

HERE = Path(__file__).parent
RESULTS_DIR = HERE.parent / "scraper-results"
IMAGES_DIR = HERE / "images"
CACHE_DIR = HERE / "cache"

MIN_SIDE = 800
MAX_SIDE = 1600
MAX_BYTES = 300_000   # 300 kB w jednostkach SI, ostrzej niż 300 KiB

log = logging.getLogger("scraper")


class ImageTooSmall(Exception):
    """Dłuższy bok poniżej MIN_SIDE (miniatura)."""


def prepare_image(dane):
    """Bajty obrazu (dowolny format) -> JPEG o dłuższym boku 800-1600 px i rozmiarze <= 300 KB.

    Miniatury (< 800 px) są odrzucane, a nie powiększane. Jakość JPEG jest obniżana
    stopniowo; jeśli to nie wystarczy, obraz jest zmniejszany o 10% (nie poniżej 800 px).
    """
    obraz = Image.open(io.BytesIO(dane))
    obraz.load()
    if max(obraz.size) < MIN_SIDE:
        raise ImageTooSmall(f"dłuższy bok {max(obraz.size)} px < {MIN_SIDE} px")

    # przezroczystość (PNG/WebP) -> białe tło, bo JPEG jej nie obsługuje
    if obraz.mode in ("RGBA", "LA", "P"):
        obraz = obraz.convert("RGBA")
        tlo = Image.new("RGB", obraz.size, "white")
        tlo.paste(obraz, mask=obraz.split()[-1])
        obraz = tlo
    else:
        obraz = obraz.convert("RGB")

    if max(obraz.size) > MAX_SIDE:
        obraz.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)  # zachowuje proporcje

    while True:
        for jakosc in (85, 80, 75, 70, 65, 60, 55, 50):
            bufor = io.BytesIO()
            obraz.save(bufor, "JPEG", quality=jakosc, optimize=True, progressive=True)
            if bufor.tell() <= MAX_BYTES:
                return bufor.getvalue()
        if max(obraz.size) <= MIN_SIDE:
            raise ValueError("nie da się zmieścić w 300 kB bez schodzenia poniżej 800 px")
        nowy_bok = max(int(max(obraz.size) * 0.9), MIN_SIDE)   # ostatnia próba dokładnie 800 px
        obraz.thumbnail((nowy_bok, nowy_bok), Image.LANCZOS)


def download_all(fetcher, produkty, folder):
    """Pobierz i przygotuj zdjęcia; istniejące pliki są pomijane (wznawianie).

    Zwraca ({id_produktu: [{"file": ..., "source_url": ...}]}, liczba błędów).
    """
    folder.mkdir(parents=True, exist_ok=True)
    pliki, bledy, wczesniej = {}, 0, 0
    for p in produkty:
        for nr, url in enumerate(p["images"], start=1):
            plik = folder / f"{p['id']}-{nr}.jpg"
            if plik.exists():
                wczesniej += 1
            else:
                try:
                    gotowe = prepare_image(fetcher.get_bytes(url))
                except Exception as e:  # błąd jednego zdjęcia nie przerywa całości
                    bledy += 1
                    log.error("Zdjęcie %s (produkt %s) pominięte: %r", url, p["id"], e)
                    continue
                tmp = plik.with_suffix(".tmp")
                tmp.write_bytes(gotowe)
                tmp.replace(plik)
            pliki.setdefault(p["id"], []).append({"file": plik.name, "source_url": url})
    log.info("Zdjęcia: %d pominiętych (gotowe z wcześniejszego przebiegu)", wczesniej)
    for p in produkty:
        if p["id"] not in pliki:  # W2: każdy produkt musi mieć co najmniej jedno zdjęcie
            log.error("Produkt %s nie ma żadnego zdjęcia", p["id"])
    return pliki, bledy


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                        handlers=[logging.FileHandler(HERE / "logs" / "images.log", encoding="utf-8"),
                                  logging.StreamHandler()])
    produkty = json.loads((RESULTS_DIR / "products.json").read_text(encoding="utf-8"))
    fetcher = Fetcher.for_site(config.BASE_URL, CACHE_DIR)

    pliki, bledy = download_all(fetcher, produkty, IMAGES_DIR)

    # spis dla skryptu importu: plik lokalny i adres źródłowy każdego zdjęcia
    spis = {str(pid): zdjecia for pid, zdjecia in pliki.items()}
    (RESULTS_DIR / "images.json").write_text(json.dumps(spis, ensure_ascii=False, indent=2), encoding="utf-8")

    razem = sum(len(n) for n in pliki.values())
    co_najmniej_2 = sum(len(n) >= 2 for n in pliki.values())
    bez_zdjec = sum(1 for p in produkty if p["id"] not in pliki)
    log.info("KONIEC: %d zdjęć gotowych, %d błędów, %d produktów bez zdjęć, %d produktów z co najmniej "
             "2 zdjęciami, %d zapytań do sieci, %d z cache",
             razem, bledy, bez_zdjec, co_najmniej_2, fetcher.network_requests, fetcher.cache_hits)


if __name__ == "__main__":
    (HERE / "logs").mkdir(exist_ok=True)
    main()
