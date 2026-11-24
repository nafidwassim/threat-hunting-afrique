"""Collecteur OSINT passif : Certificate Transparency via crt.sh (source SRC-001).
Détecte les nouveaux sous-domaines / certificats émis pour les domaines du profil.
"""
from __future__ import annotations
import json
from .. import sources


def parse(json_text: str) -> list[dict]:
    rows = json.loads(json_text) if json_text.strip() else []
    seen, out = set(), []
    for r in rows:
        for name in str(r.get("name_value", "")).splitlines():
            name = name.strip().lower().lstrip("*.")
            key = (name, r.get("id"))
            if name and key not in seen:
                seen.add(key)
                out.append({"name": name, "issuer": r.get("issuer_name", ""), "not_before": r.get("not_before", ""),
                            "crtsh_id": r.get("id")})
    return out


def new_names(current: list[dict], baseline: set[str]) -> list[dict]:
    """Noms absents de la base de référence (sous-domaines inattendus = piste de chasse)."""
    return [r for r in current if r["name"] not in baseline]


def fetch(domain: str, timeout: int = 30) -> list[dict]:
    sources.require_validated("SRC-001")
    import requests
    r = requests.get("https://crt.sh/", params={"q": f"%.{domain}", "output": "json"}, timeout=timeout,
                     headers={"User-Agent": "3pH-HESTIM-student-project"})
    r.raise_for_status()
    return parse(r.text)
