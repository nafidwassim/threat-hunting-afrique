"""Journaux versionnés : journal de collecte dark web et journal de validation (CSV, un fichier par journal)."""
from __future__ import annotations
import csv
from datetime import datetime
from pathlib import Path

JOURNALS = Path(__file__).resolve().parent.parent / "journals"

COLLECT_FIELDS = ["horodatage", "membre", "objectif", "sources_consultees", "environnement", "validation_encadrant",
                  "constats", "contenu_illicite_rencontre"]
VALIDATION_FIELDS = ["id", "date", "artefact", "objectif", "version", "test_realise", "resultat_observe", "ecart", "correction"]


def _append(path: Path, fields: list[str], row: dict) -> None:
    unknown = set(row) - set(fields)
    if unknown:
        raise ValueError(f"Champs inconnus : {sorted(unknown)}")
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in fields})


def log_collect_session(member: str, objective: str, sources: list[str], environment: str,
                        supervisor_validation: str, findings: str = "", illicit: bool = False,
                        path: Path | None = None) -> None:
    """Une ligne par session de collecte. La validation préalable de l'encadrant est obligatoire."""
    if not supervisor_validation.strip():
        raise PermissionError("Collecte refusée : la validation préalable de l'encadrant doit être renseignée "
                              "(date + référence du message/PV).")
    _append(path or JOURNALS / "journal_collecte_darkweb.csv", COLLECT_FIELDS, {
        "horodatage": datetime.now().astimezone().isoformat(timespec="seconds"), "membre": member,
        "objectif": objective, "sources_consultees": "; ".join(sources), "environnement": environment,
        "validation_encadrant": supervisor_validation, "constats": findings,
        "contenu_illicite_rencontre": "OUI - arrêt immédiat et signalement à l'encadrant" if illicit else "non"})


def log_validation(entry: dict, path: Path | None = None) -> None:
    _append(path or JOURNALS / "journal_validation.csv", VALIDATION_FIELDS, entry)
