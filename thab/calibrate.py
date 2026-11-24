"""Calibrage et évaluation des seuils de décision sur le jeu annoté.

Méthode : recherche en grille des seuils (chasse, surveillance) maximisant le F1 macro sur UN profil,
puis évaluation sur l'AUTRE profil (validation croisée entre profils : pas d'évaluation sur les données de calibrage).
"""
from __future__ import annotations
import itertools
import json
from datetime import date
from pathlib import Path

from . import classify
from .profile import load_profile, build_threat_profile
from .scoring import Scorer, load_config, decide

ROOT = Path(__file__).resolve().parent.parent
TODAY = date(2026, 11, 8)
PROFILES = {"zellige": ROOT / "config/profiles/zellige_bank_ma.yaml",
            "harmattan": ROOT / "config/profiles/harmattan_telecom_ci.yaml"}
CLASSES = ["chasse", "surveillance", "archivage"]


def item_from_row(r: dict, category: str | None = None) -> dict:
    return {"id": r["id"], "title": r["title"], "text": r["text"], "published": r["published"],
            "admiralty": r["admiralty"], "category": category or r["category"]}


def raw_scores(profile_key: str, rows: list[dict], categories: dict[str, str] | None = None) -> list[dict]:
    prof = load_profile(PROFILES[profile_key])
    tp = build_threat_profile(prof)
    cfg = load_config()
    corpus = [r["title"] + ". " + r["text"] for r in rows]
    sc = Scorer(prof, tp, cfg, corpus)
    out = []
    for r in rows:
        cat = (categories or {}).get(r["id"], r["category"])
        s = sc.score(item_from_row(r, cat), TODAY)
        s["truth"] = r["action_" + profile_key]
        out.append(s)
    return out


def _metrics(y_true: list[str], y_pred: list[str]) -> dict:
    res = {}
    for c in CLASSES:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == c and p == c)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != c and p == c)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == c and p != c)
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        res[c] = {"precision": round(pr, 3), "recall": round(rc, 3),
                  "f1": round(2 * pr * rc / (pr + rc), 3) if pr + rc else 0.0, "support": tp + fn}
    res["macro_f1"] = round(sum(res[c]["f1"] for c in CLASSES) / 3, 3)
    res["accuracy"] = round(sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true), 3)
    return res


def predict(scored: list[dict], hunt: float, watch: float, cfg: dict) -> list[str]:
    cfg2 = {**cfg, "thresholds": {"hunt": hunt, "watch": watch}}
    return [decide(s["score"], s["F"], cfg2) for s in scored]


def grid_search(scored: list[dict], cfg: dict) -> tuple[float, float, dict]:
    best = (-1.0, None, None, None)
    for hunt, watch in itertools.product(range(40, 81, 2), range(20, 61, 2)):
        if watch >= hunt:
            continue
        m = _metrics([s["truth"] for s in scored], predict(scored, hunt, watch, cfg))
        key = (m["macro_f1"], -abs(hunt - 60) - abs(watch - 40))  # à égalité : seuils proches des valeurs par défaut
        if best[1] is None or key > best[1]:
            best = (m["macro_f1"], key, (hunt, watch), m)
    return best[2][0], best[2][1], best[3]


def run(categories: dict[str, str] | None = None) -> dict:
    rows = classify.load_dataset()
    cfg = load_config()
    scored = {k: raw_scores(k, rows, categories) for k in PROFILES}
    out = {"cross_profile": {}}
    keys = list(PROFILES)
    for train_k, test_k in [(keys[0], keys[1]), (keys[1], keys[0])]:
        h, w, m_train = grid_search(scored[train_k], cfg)
        m_test = _metrics([s["truth"] for s in scored[test_k]], predict(scored[test_k], h, w, cfg))
        out["cross_profile"][f"calibré sur {train_k} -> testé sur {test_k}"] = {
            "seuils": {"chasse": h, "surveillance": w}, "train": m_train, "test": m_test}
    allscored = scored[keys[0]] + scored[keys[1]]
    h, w, m_all = grid_search(allscored, cfg)
    out["seuils_retenus_tous_profils"] = {"chasse": h, "surveillance": w, "metrics": m_all}
    d = _metrics([s["truth"] for s in allscored], predict(allscored, cfg["thresholds"]["hunt"],
                                                         cfg["thresholds"]["watch"], cfg))
    out["seuils_config_actuels"] = {**cfg["thresholds"], "metrics": d}
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
