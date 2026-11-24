"""Canaux Telegram PUBLICS (aperçu web t.me/s/<canal>) - source SRC-008.

Règles du projet : lecture passive uniquement, aucun compte, aucune interaction, aucun téléchargement de fichier.
Seuls les canaux listés dans config/sources.yaml ET validés par l'encadrant peuvent être collectés.
Ce module ne fournit que l'analyse du HTML public déjà récupéré (testable hors ligne) et une fonction
`fetch` protégée par le garde-fou `sources.require_validated`.
"""
from __future__ import annotations
import re
from html.parser import HTMLParser
from .. import sources


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.messages: list[dict] = []
        self._in_text = False
        self._cur: dict | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "")
        if tag == "div" and "tgme_widget_message_text" in cls:
            self._in_text, self._cur = True, {"text": "", "date": "", "url": ""}
        if tag == "a" and "tgme_widget_message_date" in cls:
            self._last_link = a.get("href", "")
        if tag == "time" and a.get("datetime") and self.messages is not None:
            self._last_time = a["datetime"]

    def handle_endtag(self, tag):
        if tag == "div" and self._in_text and self._cur is not None:
            self._cur["text"] = re.sub(r"\s+", " ", self._cur["text"]).strip()
            self._cur["date"] = getattr(self, "_last_time", "")
            self._cur["url"] = getattr(self, "_last_link", "")
            if self._cur["text"]:
                self.messages.append(self._cur)
            self._in_text, self._cur = False, None

    def handle_data(self, data):
        if self._in_text and self._cur is not None:
            self._cur["text"] += " " + data


def parse(html: str) -> list[dict]:
    p = _Parser()
    p.feed(html)
    return p.messages


def fetch(channel: str, timeout: int = 30) -> list[dict]:
    src = sources.require_validated("SRC-008")
    if channel not in src.get("channels", []):
        raise sources.SourceNotValidated(f"Canal {channel!r} absent de la liste validée par l'encadrant")
    import requests
    r = requests.get(f"https://t.me/s/{channel}", timeout=timeout, headers={"User-Agent": "3pH-HESTIM-student-project"})
    r.raise_for_status()
    return parse(r.text)
