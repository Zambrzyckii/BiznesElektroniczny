"""Shared helpers for PrestaShop Webservice API importers."""

from __future__ import annotations

import logging
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

DEFAULT_SHOP_URL = "http://localhost:8080"
DEFAULT_ENV_PATH = Path(__file__).resolve().parent.parent / "deploy" / ".env"


def read_env_value(env_path: Path, key: str) -> str:
    """Read a plain KEY=VALUE entry from an env file without executing it."""
    if not env_path.is_file():
        return ""
    prefix = f"{key}="
    result = ""
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip("\r").strip()
        if not line or line.startswith("#") or not line.startswith(prefix):
            continue
        value = line[len(prefix) :].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        result = value
    return result


def resolve_ws_config(
    shop_url_arg: str | None = None,
    env_path: Path = DEFAULT_ENV_PATH,
) -> tuple[str, str]:
    """Resolve (ws_key, shop_url) with CLI > os.environ > env_path > default precedence."""
    ws_key = os.environ.get("PS_WS_KEY", "").strip()
    if not ws_key:
        ws_key = read_env_value(env_path, "PS_WS_KEY").strip()

    shop_url = (shop_url_arg or "").strip()
    if not shop_url:
        shop_url = os.environ.get("PS_SHOP_URL", "").strip()
    if not shop_url:
        shop_url = read_env_value(env_path, "PS_SHOP_URL").strip()
    if not shop_url:
        shop_url = DEFAULT_SHOP_URL

    return ws_key, shop_url


def slugify(text: str, fallback: str = "item") -> str:
    """Convert text with Polish characters into a lowercase ASCII URL slug."""
    normalized = text.replace("ł", "l").replace("Ł", "L")
    ascii_text = unicodedata.normalize("NFKD", normalized).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or fallback


def raise_for_status_with_body(resp: requests.Response) -> None:
    """Log HTTP error status and response body excerpt before raising."""
    if resp.status_code >= 400:
        logger.error("Webservice HTTP %d: %s", resp.status_code, resp.text[:1000])
    resp.raise_for_status()


def set_element_text(parent: ET.Element, tag: str, value: str) -> None:
    """Set text on a child element, creating it if missing."""
    el = parent.find(tag)
    if el is None:
        el = ET.SubElement(parent, tag)
    el.text = value


def set_multilang_text(parent: ET.Element, tag: str, value: str) -> None:
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


def extract_multilang_text(node: ET.Element, tag: str) -> str:
    """Return the first non-empty <language> text inside <tag>, or plain text."""
    el = node.find(tag)
    if el is None:
        return ""
    languages = el.findall("language")
    if languages:
        for lang_el in languages:
            text = (lang_el.text or "").strip()
            if text:
                return text
        return ""
    return (el.text or "").strip()
