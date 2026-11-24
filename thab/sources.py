"""Registre des sources : garde-fou éthique. Aucune collecte sur une source non validée par l'encadrant."""
from __future__ import annotations
from pathlib import Path
import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config"


class SourceNotValidated(PermissionError):
    pass


def load(path: Path | None = None) -> dict[str, dict]:
    with open(path or CONFIG / "sources.yaml", encoding="utf-8") as f:
        return {s["id"]: s for s in yaml.safe_load(f)["sources"]}


def require_validated(source_id: str, registry: dict[str, dict] | None = None) -> dict:
    reg = registry or load()
    if source_id not in reg:
        raise SourceNotValidated(f"Source inconnue : {source_id}")
    s = reg[source_id]
    if not str(s.get("validation_status", "")).startswith("validated"):
        raise SourceNotValidated(
            f"{source_id} ({s['name']}) n'est pas validée (statut : {s.get('validation_status')}). "
            "Collecte interdite tant que l'encadrant n'a pas validé la source.")
    if s.get("access") == "tor":
        raise SourceNotValidated("Accès Tor interdit hors VM Whonix : utiliser le protocole du journal de collecte.")
    return s
