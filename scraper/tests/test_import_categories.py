"""Unit tests for PrestaShop Webservice category importer."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

import import_categories
from import_categories import (
    build_category_xml,
    main,
    parse_existing_categories,
    slugify,
)

BLANK_SCHEMA_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
  <category>
    <id/>
    <id_parent/>
    <active/>
    <id_shop_default/>
    <is_root_category/>
    <position/>
    <name>
      <language id="1"/>
      <language id="2"/>
    </name>
    <link_rewrite>
      <language id="1"/>
      <language id="2"/>
    </link_rewrite>
    <associations>
      <categories>
        <category>
          <id/>
        </category>
      </categories>
    </associations>
  </category>
</prestashop>
"""

CATEGORIES_JSON_PATH = Path(__file__).resolve().parents[2] / "scraper-results" / "categories.json"


class FakeResponse:
    """Minimal mock of requests.Response."""

    def __init__(self, content: bytes, status_code: int = 200) -> None:
        self.content = content
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AssertionError(f"Unexpected HTTP error status: {self.status_code}")


class FakeShopSession:
    """In-memory mock of requests.Session simulating PrestaShop categories API."""

    def __init__(
        self,
        initial_categories: list[dict[str, str]] | None = None,
        next_id: int = 10,
    ) -> None:
        self.auth: tuple[str, str] | None = None
        self.calls: list[dict[str, Any]] = []
        self._next_id = next_id
        self._categories: list[dict[str, str]] = list(
            initial_categories
            or [
                {"id": "1", "id_parent": "0", "is_root_category": "0", "name": "Root"},
                {"id": "2", "id_parent": "1", "is_root_category": "1", "name": "Home"},
            ]
        )

    def __enter__(self) -> FakeShopSession:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def get(self, url: str, timeout: int = 30) -> FakeResponse:
        self.calls.append({"method": "GET", "url": url, "headers": {}, "data": None, "timeout": timeout})
        if url.endswith("/api/categories?schema=blank"):
            return FakeResponse(BLANK_SCHEMA_XML)
        if url.endswith("/api/categories?display=full"):
            return FakeResponse(self._render_categories_xml())
        raise AssertionError(f"Unexpected GET URL: {url}")

    def post(
        self,
        url: str,
        data: bytes,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> FakeResponse:
        self.calls.append({"method": "POST", "url": url, "headers": headers or {}, "data": data, "timeout": timeout})
        root = ET.fromstring(data)
        cat_el = root.find("./category")
        assert cat_el is not None
        assert cat_el.find("id") is None

        new_id = str(self._next_id)
        self._next_id += 1
        entry = {
            "id": new_id,
            "id_parent": (cat_el.findtext("id_parent") or "").strip(),
            "is_root_category": (cat_el.findtext("is_root_category") or "0").strip(),
            "name": (cat_el.findtext("./name/language") or "").strip(),
        }
        self._categories.append(entry)
        resp_xml = (
            f"<?xml version='1.0' encoding='utf-8'?><prestashop><category><id>{new_id}</id></category></prestashop>"
        )
        return FakeResponse(resp_xml.encode("utf-8"), status_code=201)

    def put(
        self,
        url: str,
        data: bytes,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> FakeResponse:
        self.calls.append({"method": "PUT", "url": url, "headers": headers or {}, "data": data, "timeout": timeout})
        root = ET.fromstring(data)
        cat_el = root.find("./category")
        assert cat_el is not None
        cat_id = (cat_el.findtext("id") or "").strip()
        assert url.endswith(f"/api/categories/{cat_id}")

        for entry in self._categories:
            if entry["id"] == cat_id:
                entry["id_parent"] = (cat_el.findtext("id_parent") or "").strip()
                entry["name"] = (cat_el.findtext("./name/language") or "").strip()
                break
        return FakeResponse(data, status_code=200)

    def _render_categories_xml(self) -> bytes:
        root = ET.Element("prestashop")
        categories_el = ET.SubElement(root, "categories")
        for item in self._categories:
            cat_el = ET.SubElement(categories_el, "category")
            ET.SubElement(cat_el, "id").text = item["id"]
            ET.SubElement(cat_el, "id_parent").text = item["id_parent"]
            ET.SubElement(cat_el, "is_root_category").text = item["is_root_category"]
            name_el = ET.SubElement(cat_el, "name")
            ET.SubElement(name_el, "language", id="1").text = item["name"]
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("łŁśęąóżźćń", "llseaozzcn"),
        ("Kiełbaski, parówki i kaszanki", "kielbaski-parowki-i-kaszanki"),
        ("  Zestawy   niemięs! ", "zestawy-niemies"),
        ("---", "category"),
        ("", "category"),
    ],
)
def test_slugify(raw: str, expected: str) -> None:
    assert slugify(raw) == expected


def test_parse_existing_categories_detects_home_and_ignores_nested_associations() -> None:
    xml_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
    <prestashop>
      <categories>
        <category>
          <id>1</id>
          <id_parent>0</id_parent>
          <is_root_category>0</is_root_category>
          <name><language id="1">Root</language></name>
        </category>
        <category>
          <id>5</id>
          <id_parent>1</id_parent>
          <is_root_category>1</is_root_category>
          <name><language id="1">Home</language></name>
          <associations>
            <categories>
              <category>
                <id>99</id>
                <id_parent>5</id_parent>
                <is_root_category>0</is_root_category>
                <name><language id="1">NestedGhost</language></name>
              </category>
            </categories>
          </associations>
        </category>
        <category>
          <id>12</id>
          <id_parent>5</id_parent>
          <is_root_category>0</is_root_category>
          <name><language id="1"/><language id="2">Batony</language></name>
        </category>
      </categories>
    </prestashop>
    """
    home_id, existing = parse_existing_categories(xml_bytes)

    assert home_id == "5"
    assert existing == {
        ("0", "Root"): "1",
        ("1", "Home"): "5",
        ("5", "Batony"): "12",
    }
    assert ("5", "NestedGhost") not in existing


def test_parse_existing_categories_fallback_home_id_and_plain_name() -> None:
    xml_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
    <categories>
      <category>
        <id>10</id>
        <id_parent>2</id_parent>
        <is_root_category>0</is_root_category>
        <name>Kulki</name>
      </category>
    </categories>
    """
    home_id, existing = parse_existing_categories(xml_bytes)

    assert home_id == "2"
    assert existing == {("2", "Kulki"): "10"}


def test_build_category_xml_for_post_and_put() -> None:
    post_bytes = build_category_xml(BLANK_SCHEMA_XML, "Zdrowe śniadanie", "2", 3)
    post_root = ET.fromstring(post_bytes)
    post_cat = post_root.find("./category")
    assert post_cat is not None
    assert post_cat.find("associations") is None
    assert post_cat.find("id") is None
    assert post_cat.findtext("id_parent") == "2"
    assert post_cat.findtext("active") == "1"
    assert post_cat.findtext("is_root_category") == "0"
    assert post_cat.findtext("id_shop_default") == "1"
    assert post_cat.findtext("position") == "3"
    assert [el.text for el in post_cat.findall("./name/language")] == ["Zdrowe śniadanie", "Zdrowe śniadanie"]
    assert [el.text for el in post_cat.findall("./link_rewrite/language")] == ["zdrowe-sniadanie", "zdrowe-sniadanie"]

    put_bytes = build_category_xml(BLANK_SCHEMA_XML, "Batony", "2", 0, category_id="42")
    put_root = ET.fromstring(put_bytes)
    put_cat = put_root.find("./category")
    assert put_cat is not None
    assert put_cat.findtext("id") == "42"
    assert put_cat.find("associations") is None


def test_end_to_end_create_and_idempotent_rerun(monkeypatch: pytest.MonkeyPatch) -> None:
    ws_key = "A" * 32
    session = FakeShopSession()

    monkeypatch.setenv("PS_WS_KEY", ws_key)
    monkeypatch.setattr(import_categories.requests, "Session", lambda: session)

    exit_code = main(["--categories", str(CATEGORIES_JSON_PATH), "--shop-url", "http://localhost:8080/"])
    assert exit_code == 0
    assert session.auth == (ws_key, "")

    posts = [c for c in session.calls if c["method"] == "POST"]
    puts = [c for c in session.calls if c["method"] == "PUT"]
    assert len(posts) == 39
    assert len(puts) == 0

    for call in session.calls:
        assert ws_key not in call["url"]
        if call["method"] in ("POST", "PUT"):
            assert call["headers"].get("Content-Type") == "application/xml"

    session.calls.clear()
    exit_code_rerun = main(["--categories", str(CATEGORIES_JSON_PATH), "--shop-url", "http://localhost:8080"])
    assert exit_code_rerun == 0

    posts_rerun = [c for c in session.calls if c["method"] == "POST"]
    puts_rerun = [c for c in session.calls if c["method"] == "PUT"]
    assert len(posts_rerun) == 0
    assert len(puts_rerun) == 39


def test_mixed_create_and_update() -> None:
    categories = json.loads(CATEGORIES_JSON_PATH.read_text(encoding="utf-8"))[:2]
    # Batony (7 subcats) + Mini batoniki (6 subcats) = 2 parents + 13 subcats = 15 total
    session = FakeShopSession(
        initial_categories=[
            {"id": "1", "id_parent": "0", "is_root_category": "0", "name": "Root"},
            {"id": "2", "id_parent": "1", "is_root_category": "1", "name": "Home"},
            {"id": "10", "id_parent": "2", "is_root_category": "0", "name": "Batony"},
            {"id": "11", "id_parent": "10", "is_root_category": "0", "name": "Daktyle w posypce"},
        ],
        next_id=20,
    )

    result = import_categories.import_categories(session, "http://localhost:8080", categories)

    assert result == {"created": 13, "updated": 2}
    posts = [c for c in session.calls if c["method"] == "POST"]
    puts = [c for c in session.calls if c["method"] == "PUT"]
    assert len(posts) == 13
    assert len(puts) == 2


def test_missing_ws_key_returns_one_without_http_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def fail_session() -> Any:
        nonlocal called
        called = True
        return FakeShopSession()

    monkeypatch.delenv("PS_WS_KEY", raising=False)
    monkeypatch.setattr(import_categories.requests, "Session", fail_session)

    assert main(["--categories", str(CATEGORIES_JSON_PATH)]) == 1
    assert not called

    monkeypatch.setenv("PS_WS_KEY", "   ")
    assert main(["--categories", str(CATEGORIES_JSON_PATH)]) == 1
    assert not called
