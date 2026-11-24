"""Évaluation hors ligne des hypothèses HB-01 (password spraying) et HB-03 (connexion VPN hors profil)
sur les journaux synthétiques. Même logique que les requêtes Wazuh de hunts/wazuh/, rejouable sans SIEM.
Usage : python hunts/offline_eval.py data/generated/zellige --profile config/profiles/zellige_bank_ma.yaml
"""
from __future__ import annotations
import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import yaml

RE_FAIL = re.compile(r"^(\w{3}\s+\d+ \d\d:\d\d:\d\d) \S+ sshd\[\d+\]: Failed password for (?:invalid user )?(\S+) from (\S+)")
RE_VPN = re.compile(r"^(\S+) devname=\S+ action=tunnel-up user=(\S+) remip=(\S+) srccountry=(\w+)")


def detect_spray(auth_lines: list[str], min_users: int = 8, window_min: int = 10) -> list[dict]:
    by_ip = defaultdict(list)
    for no, line in enumerate(auth_lines, 1):
        m = RE_FAIL.match(line)
        if m:
            ts = datetime.strptime("2026 " + m.group(1), "%Y %b %d %H:%M:%S")
            by_ip[m.group(3)].append((ts, m.group(2), no))
    alerts = []
    for ip, evs in by_ip.items():
        evs.sort()
        for i, (t0, _, _) in enumerate(evs):
            win = [e for e in evs[i:] if e[0] - t0 <= timedelta(minutes=window_min)]
            users = {e[1] for e in win}
            if len(users) >= min_users:
                alerts.append({"ip": ip, "users": len(users), "first_line": win[0][2], "lines": sorted(e[2] for e in win)})
                break
    return alerts


def detect_offhours_vpn(vpn_lines: list[str], usual: set[str], hours: tuple[int, int]) -> list[dict]:
    out = []
    for no, line in enumerate(vpn_lines, 1):
        m = RE_VPN.match(line)
        if not m:
            continue
        ts = datetime.strptime(m.group(1)[:19], "%Y-%m-%dT%H:%M:%S")
        if m.group(4) not in usual and (ts.hour < hours[0] or ts.hour >= hours[1] or ts.weekday() >= 5):
            out.append({"line": no, "user": m.group(2), "country": m.group(4), "ts": ts.isoformat()})
    return out


def evaluate(folder: Path, profile: dict) -> dict:
    auth = (folder / "auth.log").read_text(encoding="utf-8").splitlines()
    vpn = (folder / "vpn.log").read_text(encoding="utf-8").splitlines()
    labels = list(csv.DictReader(open(folder / "labels.csv", encoding="utf-8")))
    truth_spray = {int(r["line_no"]) for r in labels if r["label"] == "spray_fail" and r["file"] == "auth.log"}
    truth_vpn = {int(r["line_no"]) for r in labels if r["label"] == "offhours_vpn"}
    sim = profile["simulation"]
    a = detect_spray(auth)
    flagged = {ln for al in a for ln in al["lines"]}
    v = detect_offhours_vpn(vpn, set(sim["usual_countries"]), tuple(sim["work_hours"]))
    flagged_vpn = {x["line"] for x in v}

    def prf(truth, flag):
        tp, fp, fn = len(truth & flag), len(flag - truth), len(truth - flag)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 3), "recall": round(r, 3)}

    return {"HB-01_password_spraying": {"alerts": len(a), **prf(truth_spray, flagged)},
            "HB-03_vpn_hors_profil": {"alerts": len(v), **prf(truth_vpn, flagged_vpn)}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--profile", required=True)
    a = ap.parse_args()
    print(json.dumps(evaluate(Path(a.folder), yaml.safe_load(open(a.profile, encoding="utf-8"))), indent=2))
