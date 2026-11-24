"""Normalisation d'un renseignement en bundle STIX 2.1 (JSON) sans dépendance externe.

Les identifiants sont des UUIDv5 déterministes : rejouer la collecte ne crée pas de doublons dans MISP.
Le niveau TLP et la cotation Amirauté sont portés par `labels` (étiquettes reprises telles quelles par MISP).
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone

from . import admiralty, ioc as iocmod, tlp as tlpmod

NAMESPACE = uuid.UUID("6f1c2a9e-4f3b-4c8e-9a51-0d5b7c1e2a10")  # espace de noms du projet
PRODUCER = {"type": "identity", "spec_version": "2.1", "name": "Projet 3pH Threat Hunting Afrique (HESTIM)",
            "identity_class": "organization"}


def _id(kind: str, key: str) -> str:
    return f"{kind}--{uuid.uuid5(NAMESPACE, kind + ':' + key)}"


def _ts(d: str) -> str:
    dt = datetime.fromisoformat(d)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _pattern(kind: str, value: str) -> str | None:
    v = value.replace("\\", "\\\\").replace("'", "\\'")
    return {
        "ipv4": f"[ipv4-addr:value = '{v}']",
        "domains": f"[domain-name:value = '{v}']",
        "urls": f"[url:value = '{v}']",
        "emails": f"[email-addr:value = '{v}']",
        "sha256": f"[file:hashes.'SHA-256' = '{v}']",
        "sha1": f"[file:hashes.'SHA-1' = '{v}']",
        "md5": f"[file:hashes.MD5 = '{v}']",
    }.get(kind)


def to_bundle(item: dict, score: dict | None = None, hypothesis: dict | None = None) -> dict:
    created = _ts(item["published"])
    level = tlpmod.normalize(item.get("tlp", "TLP:CLEAR"))
    labels = [tlpmod.to_misp_tag(level)] + admiralty.to_misp_tags(item["admiralty"])
    producer = {**PRODUCER, "id": _id("identity", "producer"), "created": created, "modified": created}
    objects = [producer]
    refs = []
    for kind, value in iocmod.flatten(iocmod.extract(item["text"])):
        pat = _pattern(kind, value)
        if not pat:
            continue  # les CVE sont portées par le rapport (external_references), pas par un indicator
        ind = {"type": "indicator", "spec_version": "2.1", "id": _id("indicator", value), "created": created,
               "modified": created, "created_by_ref": producer["id"], "name": f"{kind}: {value}",
               "pattern": pat, "pattern_type": "stix", "valid_from": created, "labels": labels,
               "confidence": {"A": 90, "B": 75, "C": 60, "D": 40, "E": 20, "F": 10}[item["admiralty"][0]]}
        objects.append(ind)
        refs.append(ind["id"])
    ext = [{"source_name": item.get("source", "source"), "url": item.get("url", ""),
            "description": f"Cotation {item['admiralty']}"}]
    for cve in iocmod.extract(item["text"])["cves"]:
        ext.append({"source_name": "cve", "external_id": cve})
    desc = item["text"]
    if score:
        desc += f"\n[score={score['score']} action={score['action']} P={score['P']} F={score['F']} C={score['C']}]"
    if hypothesis:
        desc += f"\n[hypothèse {hypothesis['hypothesis_id']}: " + ", ".join(
            t["id"] if isinstance(t, dict) else t for t in hypothesis["techniques"]) + "]"
    report = {"type": "report", "spec_version": "2.1", "id": _id("report", item["id"]), "created": created,
              "modified": created, "created_by_ref": producer["id"], "name": item.get("title", item["id"]),
              "description": desc, "published": created, "report_types": ["threat-report"],
              "object_refs": refs or [producer["id"]], "labels": labels, "external_references": ext}
    objects.append(report)
    return {"type": "bundle", "id": _id("bundle", item["id"]), "objects": objects}


def dumps(bundle: dict) -> str:
    return json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=False)


def validate_basic(bundle: dict) -> list[str]:
    """Contrôles minimaux de conformité STIX 2.1 (le validateur officiel 'stix2-validator' est utilisé au laboratoire)."""
    errs = []
    if bundle.get("type") != "bundle":
        errs.append("type != bundle")
    ids = {o["id"] for o in bundle["objects"]}
    for o in bundle["objects"]:
        for k in ("type", "id", "created", "modified"):
            if k not in o:
                errs.append(f"{o.get('id', '?')}: champ manquant {k}")
        if not o["id"].startswith(o["type"] + "--"):
            errs.append(f"{o['id']}: préfixe d'identifiant incohérent")
        if o["type"] == "report":
            for r in o["object_refs"]:
                if r not in ids:
                    errs.append(f"report: référence orpheline {r}")
    return errs
