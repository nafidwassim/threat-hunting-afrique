"""Chargement d'un profil d'entreprise et génération du profil de menace.

Principe de généricité : le code ne contient AUCUNE connaissance sectorielle ou nationale.
Tout est dans des fichiers de configuration ; un secteur ou un pays inconnu bascule sur le socle
commun (+ correspondance technologies -> TTP), sans modifier le code.
"""
from __future__ import annotations
import re
import unicodedata
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"

MAX_TECH_BOOST = 0.30
REQUIRED = ["id", "name", "sector", "country", "assets", "technologies"]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_profile(path: str | Path) -> dict:
    p = _load_yaml(Path(path))
    missing = [k for k in REQUIRED if k not in p]
    if missing:
        raise ValueError(f"Profil invalide, champs manquants : {missing}")
    for k in ("domains", "brands"):
        if not p["assets"].get(k):
            raise ValueError(f"Profil invalide : assets.{k} doit contenir au moins un élément")
    for d in p["assets"]["domains"]:
        if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", d.lower()):
            raise ValueError(f"Nom de domaine invalide : {d}")
    return p


def find_sector_module(sector: str, cfg: Path = CONFIG) -> dict | None:
    want = _norm(sector)
    for f in sorted((cfg / "sectors").glob("*.yaml")):
        if f.stem.startswith("_"):
            continue
        mod = _load_yaml(f)
        names = [mod.get("sector", "")] + list(mod.get("aliases", []))
        if want in {_norm(n) for n in names}:
            return mod
    return None


def find_country_module(country: str, cfg: Path = CONFIG) -> dict | None:
    f = cfg / "countries" / f"{country.upper()}.yaml"
    return _load_yaml(f) if f.exists() else None


def _merge_ttp(table: dict, entry: dict, origin: str, add: float | None = None) -> None:
    tid = entry["id"]
    is_new = tid not in table
    row = table.setdefault(tid, {"id": tid, "name": entry.get("name", tid), "tactic": entry.get("tactic", ""),
                                  "weight": 0.0, "origins": [], "why": []})
    if add is None:
        row["weight"] = max(row["weight"], float(entry["weight"]))
    else:
        # boost technologique : s'ajoute au poids existant ; une TTP nouvelle part de son poids de base
        spent = row.setdefault("_boost", 0.0)
        add = min(add, max(0.0, MAX_TECH_BOOST - spent))     # le cumul des boosts technologiques est plafonné
        row["_boost"] = spent + add
        row["weight"] = (float(entry.get("weight", 0.0)) if is_new else row["weight"]) + add
    if origin not in row["origins"]:
        row["origins"].append(origin)
    if entry.get("why"):
        row["why"].append(entry["why"])


def build_threat_profile(profile: dict, cfg: Path = CONFIG) -> dict:
    """Retourne : acteurs, TTP prioritaires, mots-clés de veille, hypothèses de départ, avertissements."""
    warnings: list[str] = []
    base = _load_yaml(cfg / "common_base.yaml")
    tech_map = _load_yaml(cfg / "tech_map.yaml")
    sector_mod = find_sector_module(profile["sector"], cfg)
    country_mod = find_country_module(profile["country"], cfg)
    if sector_mod is None:
        warnings.append(f"Aucun module sectoriel pour '{profile['sector']}' : repli sur le socle commun.")
        sector_mod = _load_yaml(cfg / "sectors" / "_generic.yaml")
    if country_mod is None:
        warnings.append(f"Aucun module pays pour '{profile['country']}' : contexte national générique.")
        country_mod = {"names": [profile["country"]], "keywords": [profile["country"]], "threat_context": []}

    ttps: dict[str, dict] = {}
    for t in base.get("ttps", []):
        _merge_ttp(ttps, t, "socle")
    for t in sector_mod.get("ttps", []):
        _merge_ttp(ttps, t, f"secteur:{sector_mod['sector']}")

    tech_hits = []
    for tech in profile.get("technologies", []):
        key = _norm(tech)
        for tkey, rule in tech_map.items():
            if _norm(tkey) in key or key in _norm(tkey):
                tech_hits.append(tech)
                for tid in rule["ttps"]:
                    entry = {"id": tid, "name": tid, "tactic": "", "why": f"{tech} : {rule['note']}"}
                    # si la TTP existe déjà on ajoute le boost, sinon on la crée avec un poids de base
                    if tid in ttps:
                        _merge_ttp(ttps, entry, f"techno:{tech}", add=rule["boost"])
                    else:
                        _merge_ttp(ttps, {**entry, "weight": 0.35}, f"techno:{tech}", add=rule["boost"])
    for row in ttps.values():
        row.pop("_boost", None)
        row["weight"] = round(min(1.0, row["weight"]), 3)

    ranked = sorted(ttps.values(), key=lambda r: (-r["weight"], r["id"]))

    actors = list(sector_mod.get("actors", []))
    keywords = []
    for src in (base.get("keywords", []), sector_mod.get("keywords", []), country_mod.get("keywords", [])):
        keywords.extend(src)
    keywords += profile["assets"]["domains"] + profile["assets"]["brands"] + list(profile.get("technologies", []))
    seen, kw = set(), []
    for k in keywords:
        if _norm(k) not in seen:
            seen.add(_norm(k))
            kw.append(k)

    fmt = {"brands": " / ".join(profile["assets"]["brands"]), "domains": " / ".join(profile["assets"]["domains"])}
    hypotheses = []
    for h in sector_mod.get("hypotheses", []):
        hypotheses.append({**h, "statement": h["statement"].format(**fmt), "origin": "module sectoriel"})
    # hypothèses issues des technologies exposées du profil (adaptation propre au profil)
    for tech in tech_hits:
        for tkey, rule in tech_map.items():
            if _norm(tkey) in _norm(tech) and rule["boost"] >= 0.15 and rule["ttps"][0] in {"T1190", "T1133"}:
                hypotheses.append({
                    "id": f"HX-{_norm(tech).replace(' ', '')[:8]}",
                    "title": f"Exploitation ou abus d'accès distant sur {tech}",
                    "techniques": rule["ttps"],
                    "data_sources": ["wazuh: journaux de l'équipement", "InternetDB: ports/CVE exposés"],
                    "statement": f"{tech} ({rule['note']}) chez {profile['name']} est ciblé via vulnérabilité ou identifiants valides.",
                    "origin": "technologie du profil",
                })
    ids = set()
    uniq = []
    for h in hypotheses:
        if h["id"] not in ids:
            ids.add(h["id"])
            uniq.append(h)

    profile_text = " ".join([
        profile["name"], profile["sector"], profile["country"], " ".join(country_mod.get("names", [])),
        " ".join(profile["assets"].get("public_services", [])), " ".join(profile["assets"].get("critical_systems", [])),
        " ".join(profile.get("technologies", [])), " ".join(sector_mod.get("keywords", [])),
        " ".join(country_mod.get("keywords", [])), " ".join(base.get("keywords", [])),
    ])
    return {
        "profile_id": profile["id"], "sector_module": sector_mod["sector"],
        "country_module": country_mod.get("country", "n/a"),
        "ttps": ranked, "actors": actors, "keywords": kw, "hypotheses": uniq,
        "country_context": country_mod.get("threat_context", []),
        "tech_hits": tech_hits, "profile_text": profile_text, "warnings": warnings,
        "sector_keywords": sector_mod.get("keywords", []), "country_keywords": country_mod.get("keywords", []),
    }
