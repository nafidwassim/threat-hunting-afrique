"""Évaluation du modèle d'anomalies : apprentissage sur logs sains (graine A), test sur logs avec attaques (graine B).
Usage : python hunts/anomaly_eval.py  -> data/generated/anomaly_report.json"""
from __future__ import annotations
import csv
import json
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from generators import normal_activity
from hunts import offline_eval
from thab.anomaly import VpnAnomalyModel, parse_vpn

PROFILES = ["zellige_bank_ma", "harmattan_telecom_ci"]


def run(profile_id: str, seeds=(11, 12, 13, 14, 15), days: int = 14) -> dict:
    prof = yaml.safe_load((ROOT / f"config/profiles/{profile_id}.yaml").read_text(encoding="utf-8"))
    rows = []
    for s in seeds:
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            normal_activity.generate(prof, days, 100 + s, t / "train", [])
            normal_activity.generate(prof, days, s, t / "test", ["spray", "offhours_vpn"])
            train = parse_vpn((t / "train/vpn.log").read_text(encoding="utf-8").splitlines())
            test = parse_vpn((t / "test/vpn.log").read_text(encoding="utf-8").splitlines())
            truth = {int(r["line_no"]) for r in csv.DictReader(open(t / "test/labels.csv", encoding="utf-8")) if r["label"] == "offhours_vpn"}
            m = VpnAnomalyModel(contamination=0.01, seed=0).fit(train)
            flag = {e["line"] for e, p in zip(test, m.predict(test)) if p}
            det = {x["line"] for x in offline_eval.detect_offhours_vpn(
                (t / "test/vpn.log").read_text(encoding="utf-8").splitlines(),
                set(prof["simulation"]["usual_countries"]), tuple(prof["simulation"]["work_hours"]))}
            def prf(f):
                tp, fp, fn = len(truth & f), len(f - truth), len(truth - f)
                return tp, fp, fn
            rows.append({"seed": s, "events": len(test), "truth": len(truth), "iforest": prf(flag), "rule": prf(det)})
    def agg(k):
        tp = sum(r[k][0] for r in rows); fp = sum(r[k][1] for r in rows); fn = sum(r[k][2] for r in rows)
        p = tp / (tp + fp) if tp + fp else 0.0; rc = tp / (tp + fn) if tp + fn else 0.0
        return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 3), "recall": round(rc, 3),
                "f1": round(2 * p * rc / (p + rc), 3) if p + rc else 0.0}
    return {"profile": profile_id, "runs": len(rows), "iforest": agg("iforest"), "rule_HB-03": agg("rule")}


if __name__ == "__main__":
    rep = {"note": "Logs 100 % synthétiques ; l'injection est simple, les valeurs sont un plancher de validation, pas une performance réelle.",
           "results": [run(p) for p in PROFILES]}
    out = ROOT / "data/generated/anomaly_report.json"
    out.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(rep, indent=2, ensure_ascii=False))
