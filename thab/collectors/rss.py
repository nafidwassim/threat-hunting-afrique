"""Flux CTI ouverts (RSS / Atom) - sources SRC-004 à SRC-007. Analyse XML durcie (pas de DTD/entités)."""
from __future__ import annotations
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

MAX_BYTES = 5_000_000


def _safe_root(xml_text: str) -> ET.Element:
    if len(xml_text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Flux trop volumineux")
    low = xml_text.lower()
    if "<!doctype" in low or "<!entity" in low:
        raise ValueError("Flux refusé : DTD / entités XML interdites (protection XXE / billion laughs)")
    return ET.fromstring(xml_text)


def _date(s: str) -> str:
    s = (s or "").strip()
    for parser in (lambda x: parsedate_to_datetime(x), lambda x: datetime.fromisoformat(x.replace("Z", "+00:00"))):
        try:
            return parser(s).date().isoformat()
        except Exception:
            continue
    return ""


def parse(xml_text: str) -> list[dict]:
    root = _safe_root(xml_text)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    items = []
    for it in root.iter("item"):
        items.append({"title": (it.findtext("title") or "").strip(), "url": (it.findtext("link") or "").strip(),
                      "published": _date(it.findtext("pubDate")), "text": (it.findtext("description") or "").strip()})
    for e in root.findall("a:entry", ns):
        link = e.find("a:link", ns)
        items.append({"title": (e.findtext("a:title", namespaces=ns) or "").strip(),
                      "url": link.get("href", "") if link is not None else "",
                      "published": _date(e.findtext("a:updated", namespaces=ns) or e.findtext("a:published", namespaces=ns)),
                      "text": (e.findtext("a:summary", namespaces=ns) or "").strip()})
    return items
