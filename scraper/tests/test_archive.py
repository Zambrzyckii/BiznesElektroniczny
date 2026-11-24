"""Testy archiwum zdjęć i wyboru przykładów."""

import zipfile

import pytest

from archive import copy_samples, make_archive, pick_samples


def test_przykladowe_zdjecia_max_20():
    pliki = {i: [{"file": f"{i}-{n}.jpg", "source_url": "x"} for n in (1, 2, 3)] for i in range(30)}
    wybrane = pick_samples(pliki)
    assert len(wybrane) == 20
    assert len(set(wybrane)) == 20


def test_najpierw_produkty_z_wieloma_zdjeciami():
    pliki = {1: [{"file": "1-1.jpg"}], 2: [{"file": "2-1.jpg"}, {"file": "2-2.jpg"}, {"file": "2-3.jpg"}]}
    assert pick_samples(pliki, ile=3) == ["2-1.jpg", "2-2.jpg", "1-1.jpg"]   # max 2 z jednego produktu


def test_kopiowanie_przykladow_czysci_stare(tmp_path):
    zdjecia, probki = tmp_path / "images", tmp_path / "sample"
    zdjecia.mkdir()
    for nazwa in ("1-1.jpg", "2-1.jpg"):
        (zdjecia / nazwa).write_bytes(b"x")
    probki.mkdir()
    (probki / "stare.jpg").write_bytes(b"x")
    copy_samples(["1-1.jpg"], zdjecia, probki)
    assert sorted(p.name for p in probki.iterdir()) == ["1-1.jpg"]


def test_brak_zdjecia_nie_kasuje_starych_przykladow(tmp_path):
    zdjecia, probki = tmp_path / "images", tmp_path / "sample"
    zdjecia.mkdir()
    probki.mkdir()
    (probki / "stare.jpg").write_bytes(b"x")
    with pytest.raises(FileNotFoundError):
        copy_samples(["1-1.jpg"], zdjecia, probki)
    assert (probki / "stare.jpg").exists()


def test_archiwum_zawiera_tylko_zdjecia_z_images_json(tmp_path):
    zdjecia = tmp_path / "images"
    zdjecia.mkdir()
    for nazwa in ("1-1.jpg", "1-2.jpg", "2-1.jpg", "9-1.tmp", "8-1.jpg"):   # 9-1.tmp: przerwany przebieg
        (zdjecia / nazwa).write_bytes(b"x")
    sciezka = make_archive(zdjecia, tmp_path / "images", ["1-1.jpg", "1-2.jpg", "2-1.jpg"])
    assert sciezka.name == "images.zip"
    assert sorted(zipfile.ZipFile(sciezka).namelist()) == ["1-1.jpg", "1-2.jpg", "2-1.jpg"]
