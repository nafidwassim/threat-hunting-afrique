"""Cotation des renseignements selon le système de l'Amirauté (fiabilité de la source A-F, crédibilité 1-6)."""
from __future__ import annotations
import re

RELIABILITY = {
    "A": "Totalement fiable",
    "B": "Habituellement fiable",
    "C": "Assez fiable",
    "D": "Pas habituellement fiable",
    "E": "Non fiable",
    "F": "Fiabilité non évaluable",
}
CREDIBILITY = {
    "1": "Confirmée par d'autres sources",
    "2": "Probablement vraie",
    "3": "Possiblement vraie",
    "4": "Douteuse",
    "5": "Improbable",
    "6": "Véracité non évaluable",
}
_PATTERN = re.compile(r"^([A-F])([1-6])$")


def parse(code: str) -> tuple[str, str]:
    """'B2' -> ('B', '2'). Lève ValueError si le code est invalide."""
    m = _PATTERN.match(code.strip().upper())
    if not m:
        raise ValueError(f"Cotation Amirauté invalide : {code!r} (attendu : lettre A-F + chiffre 1-6, ex. B2)")
    return m.group(1), m.group(2)


def label(code: str) -> str:
    r, c = parse(code)
    return f"{r}{c} - source : {RELIABILITY[r].lower()} ; information : {CREDIBILITY[c].lower()}"


def to_misp_tags(code: str) -> list[str]:
    """Étiquettes MISP (taxonomie admiralty-scale)."""
    r, c = parse(code)
    return [f'admiralty-scale:source-reliability="{r.lower()}"',
            f'admiralty-scale:information-credibility="{c}"']
