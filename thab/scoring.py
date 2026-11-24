"""Score de priorisation = pertinence pour le profil + fiabilité (Amirauté) + criticité.

score = 100 * (w_P * P + w_F * F + w_C * C), puis décision par seuils (chasse / surveillance / archivage).
Chaque composante est expliquée dans la sortie pour que l'analyste puisse contester le score.
"""
from __future__ import annotations
import math
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
import yaml

from . import admiralty
from .similarity import make_backend

CONFIG = Path(__file__).resolve().parent.parent / "config"
REGION_WORDS = ["afrique", "africa", "african", "africain"]


def load_config(path: Path | None = None) -> dict:
    with open(path or CONFIG / "scoring.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _has(text_n: str, term: str) -> bool:
    t = _norm(term).strip()
    if not t:
        return False
    if t.startswith("."):
        return re.search(re.escape(t) + r"\b", text_n) is not None
    # tolérance de flexion limitée à des suffixes précis (pluriel, féminin, gentilé) : maroc -> marocaines, banque -> banques
    suf = "" if len(t) <= 3 else r"(?:s|es|e|ain|aine|ains|aines|ien|iens|ienne|iennes|ais|aise|aises|ique|iques)?"
    return re.search(r"(?<![a-z0-9])" + re.escape(t) + suf + r"(?![a-z0-9])", text_n) is not None


def entity_score(text: str, profile: dict, tp: dict, cfg: dict) -> tuple[float, list[str]]:
    """Plus haut niveau de correspondance entre le texte et le profil + détail des correspondances."""
    w = cfg["entity_weights"]
    tn = _norm(text)
    hits: list[tuple[float, str]] = []
    for term in profile["assets"]["domains"] + profile["assets"]["brands"]:
        if _has(tn, term):
            hits.append((w["domain_or_brand"], f"actif:{term}"))
    for tech in profile.get("technologies", []):
        if _has(tn, tech):
            hits.append((w["technology"], f"techno:{tech}"))
    sector_hit = any(_has(tn, k) for k in tp["sector_keywords"]) and tp["sector_module"] != "_generic"
    country_hit = any(_has(tn, k) for k in tp["country_keywords"])
    region_hit = any(_has(tn, k) for k in REGION_WORDS)
    if sector_hit and country_hit:
        hits.append((w["sector_and_country"], "secteur+pays"))
    elif sector_hit:
        hits.append((w["sector"], "secteur"))
    elif country_hit:
        hits.append((w["country"], "pays"))
    elif region_hit:
        hits.append((w["region"], "région Afrique"))
    if not hits:
        return 0.0, []
    best = max(h[0] for h in hits)
    # noisy-or léger : plusieurs indices indépendants renforcent la correspondance
    rest = [h[0] for h in hits if h[0] != best]
    combined = 1 - (1 - best) * math.prod(1 - 0.25 * r for r in rest)
    return min(1.0, combined), [h[1] for h in hits]


def reliability_score(code: str, cfg: dict) -> float:
    r, c = admiralty.parse(code)
    return 0.5 * cfg["admiralty"]["reliability"][r] + 0.5 * cfg["admiralty"]["credibility"][c]


def criticality_score(category: str, published: str | date, today: date, cfg: dict) -> float:
    base = cfg["criticality_by_category"].get(category, 0.5)
    if isinstance(published, str):
        published = datetime.fromisoformat(published).date()
    age = max(0, (today - published).days)
    recency = math.exp(-math.log(2) * age / cfg["recency_half_life_days"])
    return base * (0.7 + 0.3 * recency)


def decide(score: float, f: float, cfg: dict) -> str:
    t = cfg["thresholds"]
    action = "chasse" if score >= t["hunt"] else "surveillance" if score >= t["watch"] else "archivage"
    if action == "chasse" and f < cfg["reliability_gate"]:
        action = "surveillance"  # source trop peu fiable : jamais de chasse prioritaire directe
    return action


class Scorer:
    def __init__(self, profile: dict, tp: dict, cfg: dict | None = None, corpus: list[str] | None = None):
        self.profile, self.tp = profile, tp
        self.cfg = cfg or load_config()
        self.sim = make_backend(self.cfg["similarity_backend"], (corpus or []) + [tp["profile_text"]])

    def score(self, item: dict, today: date | None = None) -> dict:
        cfg = self.cfg
        today = today or date.today()
        text = f"{item.get('title', '')}. {item['text']}"
        ent, hits = entity_score(text, self.profile, self.tp, cfg)
        sim_raw = self.sim.score(text, self.tp["profile_text"])
        sim = min(1.0, sim_raw / cfg["similarity_scale"])
        mix = cfg["pertinence_mix"]
        p = mix["entity"] * ent + mix["similarity"] * sim
        f = reliability_score(item["admiralty"], cfg)
        c = criticality_score(item["category"], item["published"], today, cfg)
        w = cfg["weights"]
        total = 100 * (w["pertinence"] * p + w["fiabilite"] * f + w["criticite"] * c)
        return {
            "id": item["id"], "score": round(total, 1), "action": decide(total, f, cfg),
            "P": round(p, 3), "F": round(f, 3), "C": round(c, 3),
            "detail": {"entity": round(ent, 3), "similarity_raw": round(sim_raw, 3), "similarity": round(sim, 3),
                       "hits": hits, "backend": self.sim.name},
        }
