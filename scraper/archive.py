"""Archiwum pełnego zbioru zdjęć do Releases i przykłady do repo (docs/adr/0010-image-storage.md).

Uruchomienie po images.py, w folderze scraper/:  python archive.py

- scraper/images.zip: zdjęcia wymienione w images.json, w głównym katalogu archiwum
  (<id>-<nr>.jpg; rozpakowanie do scraper/images/ odtwarza stan po images.py)
- scraper-results/sample-images/: do 20 przykładowych zdjęć, które trafiają do repo
"""

import json
import logging
import shutil
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
RESULTS_DIR = HERE.parent / "scraper-results"
IMAGES_DIR = HERE / "images"
SAMPLE_DIR = RESULTS_DIR / "sample-images"
ZIP_BASE = HERE / "images"          # -> images.zip
SAMPLE_COUNT = 20
MAX_ARCHIVE_BYTES = 1024 ** 3       # limit archiwum w Releases: 1 GB

log = logging.getLogger("scraper")


def pick_samples(pliki, ile=SAMPLE_COUNT):
    """Do `ile` przykładów, max 2 na produkt, najpierw produkty z największą galerią."""
    kolejnosc = sorted(pliki, key=lambda pid: -len(pliki[pid]))
    wybrane = []
    for pid in kolejnosc:
        for zdjecie in pliki[pid][:2]:
            if len(wybrane) < ile:
                wybrane.append(zdjecie["file"])
    return wybrane


def copy_samples(nazwy, images_dir, sample_dir):
    """Skopiuj wybrane zdjęcia do sample_dir (poprzednia zawartość jest usuwana)."""
    brak = [n for n in nazwy if not (images_dir / n).exists()]
    if brak:  # sprawdzamy przed usunięciem starych przykładów, żeby nie zostać z pustym folderem
        raise FileNotFoundError(f"brak zdjęć w {images_dir}: {', '.join(brak)} (uruchom images.py)")
    if sample_dir.exists():
        shutil.rmtree(sample_dir)
    sample_dir.mkdir(parents=True)
    for nazwa in nazwy:
        shutil.copy2(images_dir / nazwa, sample_dir / nazwa)


def make_archive(images_dir, zip_base, nazwy):
    """Spakuj zdjęcia `nazwy` z images_dir do <zip_base>.zip; zwraca ścieżkę archiwum.

    Tylko pliki z images.json: bez resztek przerwanego przebiegu (*.tmp) i zdjęć usuniętych produktów.
    """
    brak = [n for n in nazwy if not (images_dir / n).exists()]
    if brak:
        raise FileNotFoundError(f"brak zdjęć w {images_dir}: {', '.join(brak)} (uruchom images.py)")
    sciezka = Path(f"{zip_base}.zip")
    with zipfile.ZipFile(sciezka, "w", zipfile.ZIP_STORED) as zip_:  # JPEG już jest skompresowany
        for nazwa in sorted(nazwy):
            zip_.write(images_dir / nazwa, nazwa)
    if sciezka.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError(f"archiwum {sciezka} przekracza 1 GB")
    return sciezka


def main():
    (HERE / "logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                        handlers=[logging.FileHandler(HERE / "logs" / "archive.log", encoding="utf-8"),
                                  logging.StreamHandler()])
    pliki = json.loads((RESULTS_DIR / "images.json").read_text(encoding="utf-8"))
    probki = pick_samples(pliki)
    copy_samples(probki, IMAGES_DIR, SAMPLE_DIR)
    wszystkie = [z["file"] for zdjecia in pliki.values() for z in zdjecia]
    zip_path = make_archive(IMAGES_DIR, ZIP_BASE, wszystkie)
    log.info("KONIEC: %d przykładów w %s, archiwum %s: %d zdjęć, %.1f MB", len(probki), SAMPLE_DIR.name,
             zip_path.name, len(wszystkie), zip_path.stat().st_size / 1024 ** 2)


if __name__ == "__main__":
    main()
