"""Unit tests for PrestaShop Webservice product importer."""

from __future__ import annotations

import json
import logging
import math
import xml.etree.ElementTree as ET
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import pytest
import requests

import import_products
import webservice_client
from import_products import (
    DEFAULT_PRODUCTS_PATH,
    build_product_xml,
    compute_net_price,
    compute_stock_quantities,
    format_description_html,
    format_weight,
    main,
    parse_vat_group_map,
    update_product_xml,
)

BLANK_PRODUCT_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
  <product>
    <id/>
    <id_category_default/>
    <id_tax_rules_group/>
    <id_shop_default/>
    <manufacturer_name/>
    <quantity/>
    <position_in_category/>
    <type/>
    <reference/>
    <weight/>
    <price/>
    <active/>
    <state/>
    <visibility/>
    <available_for_order/>
    <show_price/>
    <minimal_quantity/>
    <indexed/>
    <name><language id="1"/><language id="2"/></name>
    <link_rewrite><language id="1"/><language id="2"/></link_rewrite>
    <description><language id="1"/><language id="2"/></description>
    <associations>
      <categories>
        <category><id/></category>
      </categories>
      <images>
        <image><id/></image>
      </images>
    </associations>
  </product>
</prestashop>
"""

CATEGORIES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<prestashop>
  <categories>
    <category>
      <id>1</id><id_parent>0</id_parent><is_root_category>0</is_root_category>
      <name><language id="1">Root</language></name>
    </category>
    <category>
      <id>2</id><id_parent>1</id_parent><is_root_category>1</is_root_category>
      <name><language id="1">Home</language></name>
    </category>
    <category>
      <id>10</id><id_parent>2</id_parent><is_root_category>0</is_root_category>
      <name><language id="1">Batony</language></name>
    </category>
    <category>
      <id>11</id><id_parent>10</id_parent><is_root_category>0</is_root_category>
      <name><language id="1">Daktyle w posypce</language></name>
    </category>
    <category>
      <id>12</id><id_parent>10</id_parent><is_root_category>0</is_root_category>
      <name><language id="1">Batony klasyczne</language></name>
    </category>
    <category>
      <id>20</id><id_parent>2</id_parent><is_root_category>0</is_root_category>
      <name><language id="1">Zdrowe śniadanie</language></name>
    </category>
    <category>
      <id>21</id><id_parent>20</id_parent><is_root_category>0</is_root_category>
      <name><language id="1">Kremy orzechowe</language></name>
    </category>
  </categories>
</prestashop>
""".encode("utf-8")

TAXES_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<prestashop>
  <taxes>
    <tax><id>1</id><rate>23.000</rate><active>1</active><deleted>0</deleted></tax>
    <tax><id>2</id><rate>8.000</rate><active>1</active><deleted>0</deleted></tax>
    <tax><id>3</id><rate>5.000</rate><active>1</active><deleted>0</deleted></tax>
    <tax><id>4</id><rate>23.000</rate><active>0</active><deleted>0</deleted></tax>
  </taxes>
</prestashop>
"""

TAX_RULE_GROUPS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<prestashop>
  <tax_rule_groups>
    <tax_rule_group><id>1</id><name>EU Standard Rate (23%)</name><active>1</active><deleted>0</deleted></tax_rule_group>
    <tax_rule_group><id>2</id><name>PL Standard Rate (23%)</name><active>1</active><deleted>0</deleted></tax_rule_group>
    <tax_rule_group><id>3</id><name>PL Reduced Rate (8%)</name><active>1</active><deleted>0</deleted></tax_rule_group>
    <tax_rule_group>
      <id>4</id><name>PL Super Reduced Rate (5%)</name><active>1</active><deleted>0</deleted>
    </tax_rule_group>
    <tax_rule_group><id>5</id><name>PL Disabled Rate (5%)</name><active>0</active><deleted>0</deleted></tax_rule_group>
  </tax_rule_groups>
</prestashop>
"""

TAX_RULES_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<prestashop>
  <tax_rules>
    <tax_rule><id>1</id><id_tax_rules_group>1</id_tax_rules_group><id_tax>1</id_tax></tax_rule>
    <tax_rule><id>2</id><id_tax_rules_group>2</id_tax_rules_group><id_tax>1</id_tax></tax_rule>
    <tax_rule><id>3</id><id_tax_rules_group>3</id_tax_rules_group><id_tax>2</id_tax></tax_rule>
    <tax_rule><id>4</id><id_tax_rules_group>4</id_tax_rules_group><id_tax>3</id_tax></tax_rule>
    <tax_rule><id>5</id><id_tax_rules_group>5</id_tax_rules_group><id_tax>3</id_tax></tax_rule>
  </tax_rules>
</prestashop>
"""

SAMPLE_PRODUCTS: list[dict[str, Any]] = [
    {
        "id": 311,
        "name": "Datesy - daktyle o smaku yuzu & cytryny",
        "description": "Pierwszy akapit.\n\nDrugi akapit <specjalny>.",
        "price_gross": 7.99,
        "old_price_gross": 8.99,
        "vat_rate": 5,
        "weight_kg": 0.035,
        "available": True,
        "category_path": ["Batony", "Daktyle w posypce"],
        "extra_categories": [["Batony", "Batony klasyczne"], ["Nieistniejąca", "Podkategoria"]],
        "attributes": {"Składniki": "daktyle & yuzu", "Waga": "35 g"},
    },
    {
        "id": 405,
        "name": "Krem orzechowy z solą",
        "description": "Gładki krem.",
        "price_gross": 19.99,
        "old_price_gross": None,
        "vat_rate": 8,
        "weight_kg": None,
        "available": False,
        "category_path": ["Zdrowe śniadanie", "Kremy orzechowe"],
        "extra_categories": [],
        "attributes": {},
    },
    {
        "id": 500,
        "name": "Zestaw śniadaniowy",
        "description": "Zestaw dla całej rodziny.",
        "price_gross": 49.90,
        "old_price_gross": 59.90,
        "vat_rate": 23,
        "weight_kg": 0.75,
        "available": True,
        "category_path": ["Zdrowe śniadanie", "Kremy orzechowe"],
        "extra_categories": [],
        "attributes": {"Cechy": "bez cukru"},
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


class FakeProductShopSession:
    """In-memory mock of PrestaShop products, categories, taxes and stock_availables API."""

    def __init__(self, initial_products: dict[str, bytes] | None = None, next_id: int = 100) -> None:
        self.auth: tuple[str, str] | None = None
        self.calls: list[dict[str, Any]] = []
        self._next_id = next_id
        self._products: dict[str, bytes] = dict(initial_products or {})
        self._stocks: dict[str, dict[str, str]] = {}
        for prod_id in self._products:
            self._stocks[prod_id] = {"id": f"9{prod_id}", "id_product": prod_id, "quantity": "0"}

    def __enter__(self) -> FakeProductShopSession:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def get(self, url: str, timeout: int = 30) -> FakeResponse:
        self.calls.append({"method": "GET", "url": url, "headers": {}, "data": None, "timeout": timeout})
        if url.endswith("/api/products?schema=blank"):
            return FakeResponse(BLANK_PRODUCT_XML)
        if url.endswith("/api/categories?display=full"):
            return FakeResponse(CATEGORIES_XML)
        if url.endswith("/api/taxes?display=full"):
            return FakeResponse(TAXES_XML)
        if url.endswith("/api/tax_rules?display=full"):
            return FakeResponse(TAX_RULES_XML)
        if url.endswith("/api/tax_rule_groups?display=full"):
            return FakeResponse(TAX_RULE_GROUPS_XML)
        if url.endswith("/api/products?display=[id,reference]"):
            return FakeResponse(self._render_products_list_xml())
        if "/api/products/" in url:
            prod_id = url.rsplit("/", 1)[-1]
            if prod_id in self._products:
                return FakeResponse(self._products[prod_id])
            return FakeResponse(b"<error>Not found</error>", status_code=404)
        if "/api/stock_availables?filter[id_product]=" in url:
            prod_id = url.split("filter[id_product]=", 1)[1].split("&", 1)[0]
            stock = self._stocks.get(prod_id)
            if stock is None:
                return FakeResponse(b"<prestashop><stock_availables/></prestashop>")
            xml = (
                "<?xml version='1.0' encoding='utf-8'?>"
                "<prestashop><stock_availables><stock_available>"
                f"<id>{stock['id']}</id>"
                f"<id_product>{stock['id_product']}</id_product>"
                "<id_product_attribute>0</id_product_attribute>"
                f"<quantity>{stock['quantity']}</quantity>"
                "</stock_available></stock_availables></prestashop>"
            )
            return FakeResponse(xml.encode("utf-8"))
        raise AssertionError(f"Unexpected GET URL: {url}")

    def post(
        self,
        url: str,
        data: bytes,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> FakeResponse:
        self.calls.append({"method": "POST", "url": url, "headers": headers or {}, "data": data, "timeout": timeout})
        assert url.endswith("/api/products")
        root = ET.fromstring(data)
        prod_el = root.find("./product")
        assert prod_el is not None
        for forbidden in ("id", "manufacturer_name", "quantity", "position_in_category", "type"):
            assert prod_el.find(forbidden) is None

        new_id = str(self._next_id)
        self._next_id += 1
        ET.SubElement(prod_el, "id").text = new_id
        ET.SubElement(prod_el, "manufacturer_name").text = ""
        ET.SubElement(prod_el, "quantity").text = "0"
        self._products[new_id] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        self._stocks[new_id] = {"id": f"9{new_id}", "id_product": new_id, "quantity": "0"}

        resp_xml = (
            f"<?xml version='1.0' encoding='utf-8'?><prestashop><product><id>{new_id}</id></product></prestashop>"
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
        if "/api/products/" in url:
            prod_el = root.find("./product")
            assert prod_el is not None
            for forbidden in ("manufacturer_name", "quantity", "position_in_category", "type"):
                assert prod_el.find(forbidden) is None
            prod_id = (prod_el.findtext("id") or "").strip()
            assert url.endswith(f"/api/products/{prod_id}")
            self._products[prod_id] = data
            return FakeResponse(data, status_code=200)
        if "/api/stock_availables/" in url:
            stock_el = root.find("./stock_available")
            assert stock_el is not None
            stock_id = (stock_el.findtext("id") or "").strip()
            assert url.endswith(f"/api/stock_availables/{stock_id}")
            prod_id = (stock_el.findtext("id_product") or "").strip()
            self._stocks[prod_id]["quantity"] = (stock_el.findtext("quantity") or "").strip()
            return FakeResponse(data, status_code=200)
        raise AssertionError(f"Unexpected PUT URL: {url}")

    def _render_products_list_xml(self) -> bytes:
        root = ET.Element("prestashop")
        products_el = ET.SubElement(root, "products")
        for prod_id, xml_bytes in self._products.items():
            prod_el = ET.fromstring(xml_bytes).find("./product")
            ref = (prod_el.findtext("reference") or "").strip() if prod_el is not None else ""
            item = ET.SubElement(products_el, "product")
            ET.SubElement(item, "id").text = prod_id
            ET.SubElement(item, "reference").text = ref
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)


@pytest.mark.parametrize(
    ("gross", "vat_rate"),
    [
        (7.99, 5),
        (19.99, 8),
        (49.90, 23),
        (12.49, 5),
        (9.99, 8),
        (149.99, 23),
    ],
)
def test_compute_net_price_round_trip_within_one_grosz(gross: float, vat_rate: int) -> None:
    net_str = compute_net_price(gross, vat_rate)
    net = Decimal(net_str)
    recomputed_gross = (net * (Decimal("1") + Decimal(vat_rate) / Decimal("100"))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    assert abs(recomputed_gross - Decimal(str(gross))) <= Decimal("0.01")


def test_compute_net_price_round_trip_for_all_scraped_products() -> None:
    products = (
        json.loads(DEFAULT_PRODUCTS_PATH.read_text(encoding="utf-8"))
        if DEFAULT_PRODUCTS_PATH.is_file()
        else SAMPLE_PRODUCTS
    )
    assert len(products) > 0
    for product in products:
        gross = Decimal(str(product["price_gross"]))
        vat_rate = int(product["vat_rate"])
        net = Decimal(compute_net_price(gross, vat_rate))
        recomputed = (net * (Decimal("1") + Decimal(vat_rate) / Decimal("100"))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        assert abs(recomputed - gross) <= Decimal("0.01"), f"Mismatch for DK-{product['id']}"


def test_parse_vat_group_map_prefers_active_pl_groups() -> None:
    vat_map = parse_vat_group_map(TAXES_XML, TAX_RULES_XML, TAX_RULE_GROUPS_XML)
    assert vat_map == {23: "2", 8: "3", 5: "4"}


def test_missing_vat_rate_raises_value_error() -> None:
    session = FakeProductShopSession()
    bad_product = dict(SAMPLE_PRODUCTS[0], vat_rate=19)
    with pytest.raises(ValueError, match="VAT rate 19%"):
        import_products.import_products(session, "http://localhost:8080", [bad_product])


def test_compute_stock_quantities_deterministic_and_bounds() -> None:
    # Case 1: all available=True (too few zeros -> bumps up to ceil(0.05 * n))
    many_available = [{"id": i, "available": True} for i in range(1, 21)]
    q1 = compute_stock_quantities(many_available, seed=42)
    q2 = compute_stock_quantities(list(reversed(many_available)), seed=42)
    assert q1 == q2
    zeros = sum(1 for v in q1.values() if v == 0)
    assert math.ceil(0.05 * 20) <= zeros <= math.floor(0.20 * 20)
    assert all(0 <= v <= 10 for v in q1.values())

    # Case 2: all available=False (too many zeros -> caps at floor(0.20 * n))
    many_unavailable = [{"id": i, "available": False} for i in range(1, 21)]
    q_unavail = compute_stock_quantities(many_unavailable, seed=42)
    zeros_unavail = sum(1 for v in q_unavail.values() if v == 0)
    assert math.ceil(0.05 * 20) <= zeros_unavail <= math.floor(0.20 * 20)
    assert all(0 <= v <= 10 for v in q_unavail.values())


def test_format_weight_and_description_html() -> None:
    assert format_weight(None) == "0"
    assert format_weight(0.035) == "0.035000"

    html_out = format_description_html(
        "Line 1 <script>\n\nLine 2 & more",
        {"Składniki": "daktyle & <orzechy>"},
    )
    assert "<script>" not in html_out
    assert "<p>Line 1 &lt;script&gt;</p><p>Line 2 &amp; more</p>" in html_out
    expected_attrs = (
        "<h3>Informacje o produkcie</h3>"
        "<ul><li><strong>Składniki:</strong> daktyle &amp; &lt;orzechy&gt;</li></ul>"
    )
    assert expected_attrs in html_out

    no_attr_html = format_description_html("Tylko opis", {})
    assert no_attr_html == "<p>Tylko opis</p>"
    assert "<h3>" not in no_attr_html


def test_build_and_update_product_xml_preserves_images_and_meta() -> None:
    post_bytes = build_product_xml(
        BLANK_PRODUCT_XML,
        SAMPLE_PRODUCTS[0],
        tax_group_id="4",
        default_cat_id="11",
        category_ids=["2", "10", "11", "12"],
    )
    post_el = ET.fromstring(post_bytes).find("./product")
    assert post_el is not None
    assert post_el.find("id") is None
    assert post_el.find("manufacturer_name") is None
    assert post_el.findtext("reference") == "DK-311"
    # Uses price_gross (7.99), not old_price_gross (8.99)
    assert post_el.findtext("price") == compute_net_price(7.99, 5)
    assert post_el.findtext("id_tax_rules_group") == "4"
    assert post_el.findtext("weight") == "0.035000"
    assert post_el.findtext("id_category_default") == "11"
    assert [el.text for el in post_el.findall("./associations/categories/category/id")] == ["2", "10", "11", "12"]
    assert post_el.findtext("./link_rewrite/language") == "datesy-daktyle-o-smaku-yuzu-cytryny"

    existing_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <prestashop>
      <product>
        <id>100</id>
        <manufacturer_name>ReadOnly</manufacturer_name>
        <quantity>5</quantity>
        <position_in_category>1</position_in_category>
        <type>simple</type>
        <reference>DK-405</reference>
        <price>10.000000</price>
        <weight>1.000000</weight>
        <id_tax_rules_group>2</id_tax_rules_group>
        <id_category_default>10</id_category_default>
        <meta_title><language id="1">Custom SEO Title</language></meta_title>
        <name><language id="1">Old Name</language></name>
        <link_rewrite><language id="1">old-name</language></link_rewrite>
        <description><language id="1">Old</language></description>
        <associations>
          <categories><category><id>2</id></category></categories>
          <images><image><id>777</id></image></images>
        </associations>
      </product>
    </prestashop>
    """
    put_bytes = update_product_xml(
        existing_xml,
        SAMPLE_PRODUCTS[1],
        tax_group_id="3",
        default_cat_id="21",
        category_ids=["2", "20", "21"],
    )
    put_el = ET.fromstring(put_bytes).find("./product")
    assert put_el is not None
    assert put_el.findtext("id") == "100"
    assert put_el.find("manufacturer_name") is None
    assert put_el.find("quantity") is None
    assert put_el.findtext("weight") == "0"
    assert put_el.findtext("id_tax_rules_group") == "3"
    assert put_el.findtext("./meta_title/language") == "Custom SEO Title"
    assert [el.text for el in put_el.findall("./associations/images/image/id")] == ["777"]
    assert [el.text for el in put_el.findall("./associations/categories/category/id")] == ["2", "20", "21"]


def test_end_to_end_create_idempotent_rerun_and_stock_updates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    products_file = tmp_path / "products.json"
    products_file.write_text(json.dumps(SAMPLE_PRODUCTS, ensure_ascii=False), encoding="utf-8")

    ws_key = "D" * 32
    session = FakeProductShopSession()
    monkeypatch.setenv("PS_WS_KEY", ws_key)
    monkeypatch.setattr(import_products.requests, "Session", lambda: session)

    cli_args = ["--products", str(products_file), "--shop-url", "http://localhost:8080", "--stock-seed", "42"]
    with caplog.at_level(logging.WARNING):
        exit_code = main(cli_args)
    assert exit_code == 0
    assert "Extra category not found" in caplog.text

    post_products = [c for c in session.calls if c["method"] == "POST" and c["url"].endswith("/api/products")]
    put_products = [c for c in session.calls if c["method"] == "PUT" and "/api/products/" in c["url"]]
    put_stocks = [c for c in session.calls if c["method"] == "PUT" and "/api/stock_availables/" in c["url"]]
    assert len(post_products) == 3
    assert len(put_products) == 0
    assert len(put_stocks) == 3

    expected_stocks = compute_stock_quantities(SAMPLE_PRODUCTS, seed=42)
    assert session._stocks["100"]["quantity"] == str(expected_stocks["DK-311"])
    assert session._stocks["101"]["quantity"] == str(expected_stocks["DK-405"])
    assert session._stocks["102"]["quantity"] == str(expected_stocks["DK-500"])
    assert session._stocks["101"]["quantity"] == "0"

    # Idempotent rerun updates all 3 products without creating duplicates
    session.calls.clear()
    assert main(["--products", str(products_file), "--shop-url", "http://localhost:8080", "--stock-seed", "42"]) == 0
    post_rerun = [c for c in session.calls if c["method"] == "POST"]
    put_prod_rerun = [c for c in session.calls if c["method"] == "PUT" and "/api/products/" in c["url"]]
    put_stock_rerun = [c for c in session.calls if c["method"] == "PUT" and "/api/stock_availables/" in c["url"]]
    assert len(post_rerun) == 0
    assert len(put_prod_rerun) == 3
    assert len(put_stock_rerun) == 3


def test_polish_slugify_and_fallback() -> None:
    assert webservice_client.slugify("Łosoś z żółtą śliwką") == "losos-z-zolta-sliwka"
    assert webservice_client.slugify("!!!", fallback="product-311") == "product-311"


def test_error_body_logged_on_http_400(caplog: pytest.LogCaptureFixture) -> None:
    class ErrorSession(FakeProductShopSession):
        def post(
            self,
            url: str,
            data: bytes,
            headers: dict[str, str] | None = None,
            timeout: int = 30,
        ) -> FakeResponse:
            body = b"<prestashop><errors><error><message>Bad product XML</message></error></errors></prestashop>"
            return FakeResponse(body, 400)

    session = ErrorSession()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(requests.HTTPError):
            import_products.import_products(session, "http://localhost:8080", SAMPLE_PRODUCTS[:1])

    assert "400" in caplog.text
    assert "Bad product XML" in caplog.text


def test_env_fallback_precedence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\nPS_WS_KEY=\"ENVFILEKEY0000000000000000000001\"\r\nPS_SHOP_URL='http://from-env-file:8080'\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("PS_WS_KEY", raising=False)
    monkeypatch.delenv("PS_SHOP_URL", raising=False)
    assert webservice_client.resolve_ws_config(None, env_path=env_file) == (
        "ENVFILEKEY0000000000000000000001",
        "http://from-env-file:8080",
    )

    monkeypatch.setenv("PS_WS_KEY", "OSENVKEY000000000000000000000002")
    monkeypatch.setenv("PS_SHOP_URL", "http://from-os-env:8080")
    assert webservice_client.resolve_ws_config(None, env_path=env_file) == (
        "OSENVKEY000000000000000000000002",
        "http://from-os-env:8080",
    )

    assert webservice_client.resolve_ws_config("http://from-cli:9090", env_path=env_file) == (
        "OSENVKEY000000000000000000000002",
        "http://from-cli:9090",
    )

    monkeypatch.delenv("PS_SHOP_URL", raising=False)
    assert webservice_client.resolve_ws_config(None, env_path=tmp_path / "missing.env") == (
        "OSENVKEY000000000000000000000002",
        webservice_client.DEFAULT_SHOP_URL,
    )
