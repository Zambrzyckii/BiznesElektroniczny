"""Unit tests for PrestaShop Webservice category importer."""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest
import requests

import import_categories
import webservice_client
from import_categories import (
    build_category_xml,
    main,
    parse_existing_categories,
    slugify,
    update_category_xml,
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

SAMPLE_CATEGORIES: list[dict[str, Any]] = [
    {
        "name": "Batony",
        "subcategories": [
            {"name": "Daktyle w posypce", "products": 4},
            {"name": "Pozostałe batony", "products": 2},
        ],
    },
    {
        "name": "Zdrowe śniadanie",
        "subcategories": [
            {"name": "Produkty śniadaniowe", "products": 7},
            {"name": "Przekąski śniadaniowe", "products": 4},
            {"name": "Kremy orzechowe", "products": 3},
        ],
    },
    {
        "name": "Zamienniki mięsa",
        "subcategories": [
            {"name": "Kiełbaski, parówki i kaszanki", "products": 4},
            {"name": "Pozostałe zamienniki mięsa", "products": 3},
        ],
    },
]


class FakeResponse:
    """Minimal mock of requests.Response."""

    def __init__(self, content: bytes, status_code: int = 200) -> None:
        self.content = content
        self.status_code = status_code

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


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
        if "/api/categories/" in url:
            cat_id = url.rsplit("/", 1)[-1]
            for item in self._categories:
                if item["id"] == cat_id:
                    return FakeResponse(self._render_single_category_xml(item))
            return FakeResponse(b"<error>Not found</error>", status_code=404)
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
            "active": (cat_el.findtext("active") or "1").strip(),
            "name": (cat_el.findtext("./name/language") or "").strip(),
            "description": (cat_el.findtext("./description/language") or "").strip(),
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
        assert cat_el.find("level_depth") is None
        assert cat_el.find("nb_products_recursive") is None
        assert cat_el.find("associations") is None
        cat_id = (cat_el.findtext("id") or "").strip()
        assert url.endswith(f"/api/categories/{cat_id}")

        for entry in self._categories:
            if entry["id"] == cat_id:
                entry["id_parent"] = (cat_el.findtext("id_parent") or "").strip()
                entry["name"] = (cat_el.findtext("./name/language") or "").strip()
                if cat_el.find("active") is not None:
                    entry["active"] = (cat_el.findtext("active") or "").strip()
                if cat_el.find("./description/language") is not None:
                    entry["description"] = (cat_el.findtext("./description/language") or "").strip()
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

    def _render_single_category_xml(self, item: dict[str, str]) -> bytes:
        root = ET.Element("prestashop")
        cat_el = ET.SubElement(root, "category")
        ET.SubElement(cat_el, "id").text = item["id"]
        ET.SubElement(cat_el, "id_parent").text = item["id_parent"]
        ET.SubElement(cat_el, "level_depth").text = "2"
        ET.SubElement(cat_el, "nb_products_recursive").text = "5"
        ET.SubElement(cat_el, "is_root_category").text = item["is_root_category"]
        ET.SubElement(cat_el, "active").text = item.get("active", "1")
        ET.SubElement(cat_el, "position").text = item.get("position", "0")
        name_el = ET.SubElement(cat_el, "name")
        ET.SubElement(name_el, "language", id="1").text = item["name"]
        lr_el = ET.SubElement(cat_el, "link_rewrite")
        ET.SubElement(lr_el, "language", id="1").text = slugify(item["name"])
        desc_el = ET.SubElement(cat_el, "description")
        ET.SubElement(desc_el, "language", id="1").text = item.get("description", "")
        meta_el = ET.SubElement(cat_el, "meta_title")
        ET.SubElement(meta_el, "language", id="1").text = item.get("meta_title", "")
        assoc_el = ET.SubElement(cat_el, "associations")
        ET.SubElement(assoc_el, "categories")
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


def test_build_category_xml_for_post_and_update_preserves_existing_fields() -> None:
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

    existing_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <prestashop>
      <category>
        <id>42</id>
        <id_parent>2</id_parent>
        <active>0</active>
        <position>9</position>
        <name><language id="1">Batony</language></name>
        <link_rewrite><language id="1">old-slug</language></link_rewrite>
        <description><language id="1">Custom editorial description</language></description>
        <meta_title><language id="1">SEO Title</language></meta_title>
        <associations><categories/></associations>
      </category>
    </prestashop>
    """
    put_bytes = update_category_xml(existing_xml, "Batony", "2", 0)
    put_root = ET.fromstring(put_bytes)
    put_cat = put_root.find("./category")
    assert put_cat is not None
    assert put_cat.findtext("id") == "42"
    assert put_cat.findtext("active") == "0"
    assert put_cat.findtext("position") == "0"
    assert put_cat.findtext("./link_rewrite/language") == "batony"
    assert put_cat.findtext("./description/language") == "Custom editorial description"
    assert put_cat.findtext("./meta_title/language") == "SEO Title"
    assert put_cat.find("associations") is None


def test_end_to_end_create_and_idempotent_rerun(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    categories_file = tmp_path / "categories.json"
    categories_file.write_text(json.dumps(SAMPLE_CATEGORIES, ensure_ascii=False), encoding="utf-8")

    ws_key = "A" * 32
    session = FakeShopSession()

    monkeypatch.setenv("PS_WS_KEY", ws_key)
    monkeypatch.setattr(import_categories.requests, "Session", lambda: session)

    exit_code = main(["--categories", str(categories_file), "--shop-url", "http://localhost:8080/"])
    assert exit_code == 0
    assert session.auth == (ws_key, "")

    posts = [c for c in session.calls if c["method"] == "POST"]
    puts = [c for c in session.calls if c["method"] == "PUT"]
    assert len(posts) == 10
    assert len(puts) == 0

    for call in session.calls:
        assert ws_key not in call["url"]
        if call["method"] in ("POST", "PUT"):
            assert call["headers"].get("Content-Type") == "application/xml"

    session.calls.clear()
    exit_code_rerun = main(["--categories", str(categories_file), "--shop-url", "http://localhost:8080"])
    assert exit_code_rerun == 0

    posts_rerun = [c for c in session.calls if c["method"] == "POST"]
    puts_rerun = [c for c in session.calls if c["method"] == "PUT"]
    assert len(posts_rerun) == 0
    assert len(puts_rerun) == 10


def test_mixed_create_and_safe_update_preserves_description_and_inactive() -> None:
    categories = SAMPLE_CATEGORIES[:2]
    session = FakeShopSession(
        initial_categories=[
            {"id": "1", "id_parent": "0", "is_root_category": "0", "name": "Root"},
            {"id": "2", "id_parent": "1", "is_root_category": "1", "name": "Home"},
            {
                "id": "10",
                "id_parent": "2",
                "is_root_category": "0",
                "name": "Batony",
                "active": "0",
                "description": "Keep this description",
            },
            {"id": "11", "id_parent": "10", "is_root_category": "0", "name": "Daktyle w posypce"},
        ],
        next_id=20,
    )

    result = import_categories.import_categories(session, "http://localhost:8080", categories)

    assert result == {"created": 5, "updated": 2}
    posts = [c for c in session.calls if c["method"] == "POST"]
    puts = [c for c in session.calls if c["method"] == "PUT"]
    get_single = [c for c in session.calls if c["method"] == "GET" and "/api/categories/" in c["url"]]
    assert len(posts) == 5
    assert len(puts) == 2
    assert len(get_single) == 2

    batony_put = next(c for c in puts if c["url"].endswith("/api/categories/10"))
    batony_el = ET.fromstring(batony_put["data"]).find("./category")
    assert batony_el is not None
    assert batony_el.findtext("active") == "0"
    assert batony_el.findtext("./description/language") == "Keep this description"


def test_error_body_logged_on_http_400(caplog: pytest.LogCaptureFixture) -> None:
    class ErrorSession(FakeShopSession):
        def post(
            self,
            url: str,
            data: bytes,
            headers: dict[str, str] | None = None,
            timeout: int = 30,
        ) -> FakeResponse:
            body = b"<prestashop><errors><error><message>Invalid XML field</message></error></errors></prestashop>"
            return FakeResponse(body, 400)

    session = ErrorSession()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(requests.HTTPError):
            import_categories.import_categories(session, "http://localhost:8080", SAMPLE_CATEGORIES[:1])

    assert "400" in caplog.text
    assert "Invalid XML field" in caplog.text


def test_env_file_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# Comment line\n\nPS_WS_KEY='B" + "C" * 31 + "'\r\nPS_SHOP_URL=\"http://example.local:8080\"\n",
        encoding="utf-8",
    )
    categories_file = tmp_path / "categories.json"
    categories_file.write_text(json.dumps(SAMPLE_CATEGORIES[:1], ensure_ascii=False), encoding="utf-8")

    session = FakeShopSession()
    monkeypatch.delenv("PS_WS_KEY", raising=False)
    monkeypatch.delenv("PS_SHOP_URL", raising=False)
    monkeypatch.setattr(webservice_client, "DEFAULT_ENV_PATH", env_file)
    monkeypatch.setattr(
        import_categories,
        "resolve_ws_config",
        lambda shop_url_arg=None: webservice_client.resolve_ws_config(shop_url_arg, env_path=env_file),
    )
    monkeypatch.setattr(import_categories.requests, "Session", lambda: session)

    assert main(["--categories", str(categories_file)]) == 0
    assert session.auth == ("B" + "C" * 31, "")
    assert any(c["url"].startswith("http://example.local:8080/api/categories") for c in session.calls)


def test_missing_ws_key_returns_one_without_http_calls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    categories_file = tmp_path / "categories.json"
    categories_file.write_text(json.dumps(SAMPLE_CATEGORIES, ensure_ascii=False), encoding="utf-8")
    missing_env = tmp_path / "nonexistent.env"
    called = False

    def fail_session() -> Any:
        nonlocal called
        called = True
        return FakeShopSession()

    monkeypatch.delenv("PS_WS_KEY", raising=False)
    monkeypatch.setattr(
        import_categories,
        "resolve_ws_config",
        lambda shop_url_arg=None: webservice_client.resolve_ws_config(shop_url_arg, env_path=missing_env),
    )
    monkeypatch.setattr(import_categories.requests, "Session", fail_session)

    assert main(["--categories", str(categories_file)]) == 1
    assert not called

    monkeypatch.setenv("PS_WS_KEY", "   ")
    assert main(["--categories", str(categories_file)]) == 1
    assert not called
