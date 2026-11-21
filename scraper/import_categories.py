"""Import category tree from JSON into PrestaShop via the Webservice API."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_CATEGORIES_PATH = Path(__file__).resolve().parent.parent / "scraper-results" / "categories.json"
DEFAULT_SHOP_URL = "http://localhost:8080"


def slugify(text: str) -> str:
    """Convert a category name into a lowercase ASCII URL slug."""
    normalized = text.replace("ł", "l").replace("Ł", "L")
    ascii_text = unicodedata.normalize("NFKD", normalized).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or "category"


def _extract_category_name(node: ET.Element) -> str:
    """Return the first non-empty localized name or plain <name> text."""
    name_el = node.find("name")
    if name_el is None:
        return ""
    lang_els = name_el.findall("language")
    if lang_els:
        for lang_el in lang_els:
            text = (lang_el.text or "").strip()
            if text:
                return text
        return ""
    return (name_el.text or "").strip()


def parse_existing_categories(xml_bytes: bytes) -> tuple[str, dict[tuple[str, str], str]]:
    """Parse PrestaShop categories XML into (home_id, {(id_parent, name): category_id})."""
    root = ET.fromstring(xml_bytes)
    category_nodes = root.findall("./categories/category")
    if not category_nodes:
        category_nodes = root.findall("./category")

    home_id: str | None = None
    existing: dict[tuple[str, str], str] = {}

    for node in category_nodes:
        cat_id = (node.findtext("id") or "").strip()
        id_parent = (node.findtext("id_parent") or "").strip()
        is_root = (node.findtext("is_root_category") or "").strip()
        name = _extract_category_name(node)

        if is_root == "1" and cat_id and home_id is None:
            home_id = cat_id

        if cat_id and id_parent and name:
            existing[(id_parent, name)] = cat_id

    return (home_id or "2"), existing


def _set_element_text(parent: ET.Element, tag: str, value: str) -> None:
    """Set text on a child element, creating it if missing."""
    el = parent.find(tag)
    if el is None:
        el = ET.SubElement(parent, tag)
    el.text = value


def _set_multilang_text(parent: ET.Element, tag: str, value: str) -> None:
    """Populate all <language> children inside a field, or its text if none exist."""
    el = parent.find(tag)
    if el is None:
        el = ET.SubElement(parent, tag)
    languages = el.findall("language")
    if languages:
        for lang_el in languages:
            lang_el.text = value
    else:
        el.text = value


def build_category_xml(
    blank_xml_bytes: bytes,
    name: str,
    id_parent: str,
    position: int,
    category_id: str | None = None,
) -> bytes:
    """Build a UTF-8 XML payload for creating or updating a PrestaShop category."""
    root = ET.fromstring(blank_xml_bytes)
    category = root.find("./category")
    if category is None:
        raise ValueError("Blank schema XML does not contain ./category")

    associations = category.find("associations")
    if associations is not None:
        category.remove(associations)

    id_el = category.find("id")
    if category_id is not None:
        if id_el is None:
            id_el = ET.SubElement(category, "id")
        id_el.text = str(category_id)
    elif id_el is not None:
        category.remove(id_el)

    _set_element_text(category, "id_parent", str(id_parent))
    _set_element_text(category, "active", "1")
    _set_element_text(category, "is_root_category", "0")
    _set_element_text(category, "id_shop_default", "1")
    _set_element_text(category, "position", str(position))
    _set_multilang_text(category, "name", name)
    _set_multilang_text(category, "link_rewrite", slugify(name))

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _upsert_category(
    session: requests.Session,
    base_url: str,
    blank_xml: bytes,
    existing: dict[tuple[str, str], str],
    name: str,
    id_parent: str,
    position: int,
    timeout: int,
) -> tuple[str, bool]:
    """Create or update a single category, returning (category_id, created)."""
    key = (id_parent, name)
    headers = {"Content-Type": "application/xml"}
    existing_id = existing.get(key)

    if existing_id is not None:
        payload = build_category_xml(blank_xml, name, id_parent, position, category_id=existing_id)
        resp = session.put(
            f"{base_url}/api/categories/{existing_id}",
            data=payload,
            headers=headers,
            timeout=timeout,
        )
        resp.raise_for_status()
        return existing_id, False

    payload = build_category_xml(blank_xml, name, id_parent, position)
    resp = session.post(
        f"{base_url}/api/categories",
        data=payload,
        headers=headers,
        timeout=timeout,
    )
    resp.raise_for_status()

    resp_root = ET.fromstring(resp.content)
    new_id = (resp_root.findtext("./category/id") or "").strip()
    if not new_id:
        raise ValueError(f"Missing ./category/id in POST response for {name!r}")
    existing[key] = new_id
    return new_id, True


def import_categories(
    session: requests.Session,
    shop_url: str,
    categories: list[dict[str, Any]],
    timeout: int = 30,
) -> dict[str, int]:
    """Import top-level and child categories idempotently into PrestaShop."""
    base_url = shop_url.rstrip("/")

    blank_resp = session.get(f"{base_url}/api/categories?schema=blank", timeout=timeout)
    blank_resp.raise_for_status()
    blank_xml = blank_resp.content

    list_resp = session.get(f"{base_url}/api/categories?display=full", timeout=timeout)
    list_resp.raise_for_status()
    home_id, existing = parse_existing_categories(list_resp.content)

    created = 0
    updated = 0

    for parent_pos, cat in enumerate(categories):
        parent_id, parent_created = _upsert_category(
            session, base_url, blank_xml, existing, cat["name"], home_id, parent_pos, timeout
        )
        if parent_created:
            created += 1
        else:
            updated += 1

        for sub_pos, sub in enumerate(cat.get("subcategories", [])):
            _, sub_created = _upsert_category(
                session, base_url, blank_xml, existing, sub["name"], parent_id, sub_pos, timeout
            )
            if sub_created:
                created += 1
            else:
                updated += 1

    logger.info("Categories imported: %d created, %d updated", created, updated)
    return {"created": created, "updated": updated}


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for importing categories into PrestaShop."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Import categories into PrestaShop via Webservice API.")
    parser.add_argument(
        "--categories",
        type=Path,
        default=DEFAULT_CATEGORIES_PATH,
        help="Path to categories.json file.",
    )
    parser.add_argument(
        "--shop-url",
        default=os.environ.get("PS_SHOP_URL", DEFAULT_SHOP_URL),
        help="Base URL of the PrestaShop instance.",
    )
    args = parser.parse_args(argv)

    ws_key = os.environ.get("PS_WS_KEY", "").strip()
    if not ws_key:
        logger.error("PS_WS_KEY environment variable is required")
        return 1

    try:
        categories = json.loads(args.categories.read_text(encoding="utf-8"))
        with requests.Session() as session:
            session.auth = (ws_key, "")
            import_categories(session, args.shop_url, categories)
    except (requests.RequestException, OSError, ET.ParseError, ValueError) as exc:
        logger.error("Category import failed: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
