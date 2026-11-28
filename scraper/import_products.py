"""Import products with prices, VAT, weight and stock into PrestaShop via Webservice API."""

from __future__ import annotations

import argparse
import html
import json
import logging
import math
import random
import sys
import xml.etree.ElementTree as ET
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import requests

from import_categories import parse_existing_categories
from webservice_client import (
    raise_for_status_with_body,
    resolve_ws_config,
    set_element_text,
    set_multilang_text,
    slugify,
)

logger = logging.getLogger(__name__)

DEFAULT_PRODUCTS_PATH = Path(__file__).resolve().parent.parent / "scraper-results" / "products.json"
DEFAULT_STOCK_SEED = 42

POST_READONLY_TAGS = ("manufacturer_name", "quantity", "position_in_category", "type", "id")
PUT_READONLY_TAGS = ("manufacturer_name", "quantity", "position_in_category", "type")


def product_reference(product: dict[str, Any]) -> str:
    """Return the stable PrestaShop reference key for a scraped product."""
    return f"DK-{product['id']}"


def compute_net_price(price_gross: float | int | str | Decimal, vat_rate: int) -> str:
    """Compute net price rounded to 6 decimal places using ROUND_HALF_UP."""
    gross = Decimal(str(price_gross))
    divisor = Decimal("1") + Decimal(str(vat_rate)) / Decimal("100")
    net = (gross / divisor).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return f"{net:.6f}"


def format_weight(weight_kg: float | int | str | Decimal | None) -> str:
    """Format product weight in kg for PrestaShop XML."""
    if weight_kg is None:
        return "0"
    return f"{Decimal(str(weight_kg)):.6f}"


def format_description_html(description: str, attributes: dict[str, str] | None = None) -> str:
    """Format product description and optional attributes table as escaped HTML."""
    parts: list[str] = []
    for raw_line in (description or "").splitlines():
        line = raw_line.strip()
        if line:
            parts.append(f"<p>{html.escape(line)}</p>")

    if attributes:
        items = "".join(
            f"<li><strong>{html.escape(str(key))}:</strong> {html.escape(str(value))}</li>"
            for key, value in attributes.items()
        )
        parts.append(f"<h3>Informacje o produkcie</h3><ul>{items}</ul>")

    return "".join(parts)


def compute_stock_quantities(products: list[dict[str, Any]], seed: int = DEFAULT_STOCK_SEED) -> dict[str, int]:
    """Assign deterministic stock quantities (0..10) with 5-20% zero-stock items for n >= 5."""
    ordered = sorted(products, key=product_reference)
    n = len(ordered)
    zero_refs: list[str] = []
    nonzero_refs: list[str] = []

    for product in ordered:
        ref = product_reference(product)
        if product.get("available") is False:
            zero_refs.append(ref)
        else:
            nonzero_refs.append(ref)

    rng = random.Random(seed)
    zero_set = set(zero_refs)

    if n >= 5:
        min_zeros = math.ceil(0.05 * n)
        max_zeros = math.floor(0.20 * n)
        if len(zero_set) < min_zeros:
            needed = min_zeros - len(zero_set)
            zero_set.update(rng.sample(nonzero_refs, needed))
        elif len(zero_set) > max_zeros:
            excess = len(zero_set) - max_zeros
            for ref in rng.sample(zero_refs, excess):
                zero_set.remove(ref)

    quantities: dict[str, int] = {}
    for product in ordered:
        ref = product_reference(product)
        quantities[ref] = 0 if ref in zero_set else rng.randint(1, 10)
    return quantities


def parse_vat_group_map(
    taxes_xml: bytes,
    tax_rules_xml: bytes,
    tax_rule_groups_xml: bytes,
) -> dict[int, str]:
    """Map integer VAT rates (e.g. 5, 8, 23) to active PrestaShop id_tax_rules_group."""
    taxes_root = ET.fromstring(taxes_xml)
    tax_nodes = taxes_root.findall("./taxes/tax") or taxes_root.findall("./tax")
    active_taxes: dict[str, int] = {}
    for node in tax_nodes:
        tax_id = (node.findtext("id") or "").strip()
        active = (node.findtext("active") or "").strip()
        deleted = (node.findtext("deleted") or "0").strip()
        rate_text = (node.findtext("rate") or "").strip()
        if not tax_id or active != "1" or deleted == "1" or not rate_text:
            continue
        rate_dec = Decimal(rate_text)
        if rate_dec == rate_dec.to_integral_value():
            active_taxes[tax_id] = int(rate_dec)

    groups_root = ET.fromstring(tax_rule_groups_xml)
    group_nodes = groups_root.findall("./tax_rule_groups/tax_rule_group") or groups_root.findall("./tax_rule_group")
    active_groups: dict[str, str] = {}
    for node in group_nodes:
        group_id = (node.findtext("id") or "").strip()
        active = (node.findtext("active") or "").strip()
        deleted = (node.findtext("deleted") or "0").strip()
        name = (node.findtext("name") or "").strip()
        if group_id and active == "1" and deleted != "1":
            active_groups[group_id] = name

    rules_root = ET.fromstring(tax_rules_xml)
    rule_nodes = rules_root.findall("./tax_rules/tax_rule") or rules_root.findall("./tax_rule")
    candidates: dict[int, dict[str, str]] = {}
    for node in rule_nodes:
        group_id = (node.findtext("id_tax_rules_group") or "").strip()
        tax_id = (node.findtext("id_tax") or "").strip()
        if group_id in active_groups and tax_id in active_taxes:
            rate = active_taxes[tax_id]
            candidates.setdefault(rate, {})[group_id] = active_groups[group_id]

    vat_map: dict[int, str] = {}
    for rate, group_entries in candidates.items():
        best_id = sorted(
            group_entries.keys(),
            key=lambda gid: ("PL" not in group_entries[gid].upper(), int(gid)),
        )[0]
        vat_map[rate] = best_id
    return vat_map


def parse_existing_products(xml_bytes: bytes) -> dict[str, str]:
    """Parse /api/products?display=[id,reference] XML into {reference: product_id}."""
    root = ET.fromstring(xml_bytes)
    product_nodes = root.findall("./products/product") or root.findall("./product")
    existing: dict[str, str] = {}
    for node in product_nodes:
        prod_id = (node.findtext("id") or "").strip()
        ref = (node.findtext("reference") or "").strip()
        if prod_id and ref:
            existing[ref] = prod_id
    return existing


def _resolve_category_pair(
    home_id: str,
    categories_map: dict[tuple[str, str], str],
    parent_name: str,
    sub_name: str,
) -> tuple[str, str] | None:
    """Resolve (parent_name, sub_name) to (parent_id, sub_id), or None if missing."""
    parent_id = categories_map.get((home_id, parent_name))
    if parent_id is None:
        return None
    sub_id = categories_map.get((parent_id, sub_name))
    if sub_id is None:
        return None
    return parent_id, sub_id


def resolve_product_categories(
    product: dict[str, Any],
    home_id: str,
    categories_map: dict[tuple[str, str], str],
) -> tuple[str, list[str]]:
    """Return (id_category_default, unique_category_ids) for a product."""
    cat_path = product.get("category_path") or []
    if len(cat_path) != 2:
        raise ValueError(f"Invalid category_path for {product_reference(product)}: {cat_path!r}")

    primary = _resolve_category_pair(home_id, categories_map, cat_path[0], cat_path[1])
    if primary is None:
        raise ValueError(f"Primary category not found for {product_reference(product)}: {cat_path!r}")

    parent_id, sub_id = primary
    ordered_ids: list[str] = []
    for cid in (home_id, parent_id, sub_id):
        if cid not in ordered_ids:
            ordered_ids.append(cid)

    for extra in product.get("extra_categories") or []:
        if len(extra) != 2:
            logger.warning("Skipping invalid extra_category %r for %s", extra, product_reference(product))
            continue
        resolved = _resolve_category_pair(home_id, categories_map, extra[0], extra[1])
        if resolved is None:
            logger.warning("Extra category not found for %s: %r", product_reference(product), extra)
            continue
        for cid in resolved:
            if cid not in ordered_ids:
                ordered_ids.append(cid)

    return sub_id, ordered_ids


def _set_product_categories(product_el: ET.Element, category_ids: list[str]) -> None:
    """Replace associations/categories while preserving other associations such as images."""
    associations = product_el.find("associations")
    if associations is None:
        associations = ET.SubElement(product_el, "associations")

    old_categories = associations.find("categories")
    if old_categories is not None:
        associations.remove(old_categories)

    categories_el = ET.SubElement(associations, "categories")
    for cid in category_ids:
        cat_el = ET.SubElement(categories_el, "category")
        ET.SubElement(cat_el, "id").text = str(cid)


def _apply_common_product_fields(
    product_el: ET.Element,
    product: dict[str, Any],
    tax_group_id: str,
    default_cat_id: str,
    category_ids: list[str],
) -> None:
    """Populate importer-managed product fields on a <product> element."""
    ref = product_reference(product)
    name = product["name"]
    description_html = format_description_html(product.get("description", ""), product.get("attributes"))

    set_element_text(product_el, "reference", ref)
    set_multilang_text(product_el, "name", name)
    set_multilang_text(product_el, "link_rewrite", slugify(name, fallback=f"product-{product['id']}"))
    set_multilang_text(product_el, "description", description_html)
    set_element_text(product_el, "price", compute_net_price(product["price_gross"], int(product["vat_rate"])))
    set_element_text(product_el, "id_tax_rules_group", str(tax_group_id))
    set_element_text(product_el, "weight", format_weight(product.get("weight_kg")))
    set_element_text(product_el, "id_category_default", str(default_cat_id))
    set_element_text(product_el, "active", "1")
    set_element_text(product_el, "state", "1")
    _set_product_categories(product_el, category_ids)


def build_product_xml(
    blank_xml_bytes: bytes,
    product: dict[str, Any],
    tax_group_id: str,
    default_cat_id: str,
    category_ids: list[str],
) -> bytes:
    """Build a UTF-8 XML payload for creating a new PrestaShop product."""
    root = ET.fromstring(blank_xml_bytes)
    product_el = root.find("./product")
    if product_el is None:
        raise ValueError("Blank schema XML does not contain ./product")

    for tag in POST_READONLY_TAGS:
        el = product_el.find(tag)
        if el is not None:
            product_el.remove(el)

    _apply_common_product_fields(product_el, product, tax_group_id, default_cat_id, category_ids)
    set_element_text(product_el, "visibility", "both")
    set_element_text(product_el, "available_for_order", "1")
    set_element_text(product_el, "show_price", "1")
    set_element_text(product_el, "minimal_quantity", "1")
    set_element_text(product_el, "id_shop_default", "1")
    set_element_text(product_el, "indexed", "1")

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def update_product_xml(
    existing_xml_bytes: bytes,
    product: dict[str, Any],
    tax_group_id: str,
    default_cat_id: str,
    category_ids: list[str],
) -> bytes:
    """Update only importer-managed fields on an existing PrestaShop product XML."""
    root = ET.fromstring(existing_xml_bytes)
    product_el = root.find("./product")
    if product_el is None:
        raise ValueError("Existing product XML does not contain ./product")

    for tag in PUT_READONLY_TAGS:
        el = product_el.find(tag)
        if el is not None:
            product_el.remove(el)

    _apply_common_product_fields(product_el, product, tax_group_id, default_cat_id, category_ids)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _update_stock_available(
    session: requests.Session,
    base_url: str,
    product_id: str,
    quantity: int,
    timeout: int,
) -> None:
    """Fetch and update the stock_available record for a product."""
    url = f"{base_url}/api/stock_availables?filter[id_product]={product_id}&filter[id_product_attribute]=0&display=full"
    resp = session.get(url, timeout=timeout)
    raise_for_status_with_body(resp)

    root = ET.fromstring(resp.content)
    stock_el = root.find("./stock_availables/stock_available")
    if stock_el is None:
        stock_el = root.find("./stock_available")
    if stock_el is None:
        raise ValueError(f"No stock_available found for product id={product_id}")

    stock_id = (stock_el.findtext("id") or "").strip()
    if not stock_id:
        raise ValueError(f"Missing stock_available id for product id={product_id}")

    set_element_text(stock_el, "quantity", str(quantity))
    payload_root = ET.Element("prestashop")
    payload_root.append(stock_el)
    payload = ET.tostring(payload_root, encoding="utf-8", xml_declaration=True)

    put_resp = session.put(
        f"{base_url}/api/stock_availables/{stock_id}",
        data=payload,
        headers={"Content-Type": "application/xml"},
        timeout=timeout,
    )
    raise_for_status_with_body(put_resp)


def import_products(
    session: requests.Session,
    shop_url: str,
    products: list[dict[str, Any]],
    stock_seed: int = DEFAULT_STOCK_SEED,
    timeout: int = 30,
) -> dict[str, int]:
    """Import products with prices, VAT, weight and stock idempotently into PrestaShop."""
    base_url = shop_url.rstrip("/")

    blank_resp = session.get(f"{base_url}/api/products?schema=blank", timeout=timeout)
    raise_for_status_with_body(blank_resp)
    blank_xml = blank_resp.content

    cats_resp = session.get(f"{base_url}/api/categories?display=full", timeout=timeout)
    raise_for_status_with_body(cats_resp)
    home_id, categories_map = parse_existing_categories(cats_resp.content)

    taxes_resp = session.get(f"{base_url}/api/taxes?display=full", timeout=timeout)
    raise_for_status_with_body(taxes_resp)
    tax_rules_resp = session.get(f"{base_url}/api/tax_rules?display=full", timeout=timeout)
    raise_for_status_with_body(tax_rules_resp)
    tax_groups_resp = session.get(f"{base_url}/api/tax_rule_groups?display=full", timeout=timeout)
    raise_for_status_with_body(tax_groups_resp)
    vat_map = parse_vat_group_map(taxes_resp.content, tax_rules_resp.content, tax_groups_resp.content)

    existing_resp = session.get(f"{base_url}/api/products?display=[id,reference]", timeout=timeout)
    raise_for_status_with_body(existing_resp)
    existing_products = parse_existing_products(existing_resp.content)

    stock_quantities = compute_stock_quantities(products, seed=stock_seed)
    headers = {"Content-Type": "application/xml"}

    created = 0
    updated = 0

    for product in products:
        ref = product_reference(product)
        vat_rate = int(product["vat_rate"])
        tax_group_id = vat_map.get(vat_rate)
        if tax_group_id is None:
            raise ValueError(f"No active tax rules group found for VAT rate {vat_rate}% ({ref})")

        default_cat_id, category_ids = resolve_product_categories(product, home_id, categories_map)
        existing_id = existing_products.get(ref)

        if existing_id is not None:
            get_resp = session.get(f"{base_url}/api/products/{existing_id}", timeout=timeout)
            raise_for_status_with_body(get_resp)
            payload = update_product_xml(get_resp.content, product, tax_group_id, default_cat_id, category_ids)
            put_resp = session.put(
                f"{base_url}/api/products/{existing_id}",
                data=payload,
                headers=headers,
                timeout=timeout,
            )
            raise_for_status_with_body(put_resp)
            product_id = existing_id
            updated += 1
        else:
            payload = build_product_xml(blank_xml, product, tax_group_id, default_cat_id, category_ids)
            post_resp = session.post(
                f"{base_url}/api/products",
                data=payload,
                headers=headers,
                timeout=timeout,
            )
            raise_for_status_with_body(post_resp)
            resp_root = ET.fromstring(post_resp.content)
            product_id = (resp_root.findtext("./product/id") or "").strip()
            if not product_id:
                raise ValueError(f"Missing ./product/id in POST response for {ref}")
            existing_products[ref] = product_id
            created += 1

        _update_stock_available(session, base_url, product_id, stock_quantities[ref], timeout)

    logger.info("Products imported: %d created, %d updated", created, updated)
    return {"created": created, "updated": updated}


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for importing products into PrestaShop."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Import products into PrestaShop via Webservice API.")
    parser.add_argument(
        "--products",
        type=Path,
        default=DEFAULT_PRODUCTS_PATH,
        help="Path to products.json file.",
    )
    parser.add_argument(
        "--shop-url",
        default=None,
        help="Base URL of the PrestaShop instance.",
    )
    parser.add_argument(
        "--stock-seed",
        type=int,
        default=DEFAULT_STOCK_SEED,
        help="Seed for deterministic stock quantity assignment.",
    )
    args = parser.parse_args(argv)

    ws_key, shop_url = resolve_ws_config(args.shop_url)
    if not ws_key:
        logger.error("PS_WS_KEY is required (set in environment or deploy/.env)")
        return 1

    try:
        products = json.loads(args.products.read_text(encoding="utf-8"))
        with requests.Session() as session:
            session.auth = (ws_key, "")
            import_products(session, shop_url, products, stock_seed=args.stock_seed)
    except (requests.RequestException, OSError, ET.ParseError, ValueError) as exc:
        logger.error("Product import failed: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
