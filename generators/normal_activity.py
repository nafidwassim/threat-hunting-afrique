"""Générateur de journaux SYNTHÉTIQUES pour une entreprise fictive (aucune donnée réelle, aucune donnée personnelle).

Produit, à partir du seul fichier de profil (section `simulation`), dans --out :
  auth.log          sshd / sudo / cron au format syslog (décodeurs Wazuh standard)
  vpn.log           connexions VPN, format clé=valeur (décodeur personnalisé à écrire côté Wazuh)
  web_access.log    accès web (nginx, format combined)
  winevents.jsonl   événements Windows 4624/4625 simplifiés (un JSON par ligne)
  labels.csv        vérité terrain des scénarios d'attaque injectés (pour évaluer les chasses)

Scénarios injectables (--inject) : spray (password spraying puis succès), offhours_vpn (connexion VPN nocturne depuis
un pays inhabituel). Les attaques réelles (Kali, Atomic Red Team) sont rejouées au laboratoire ; ceci est la version
journaux seuls, reproductible et sans danger.
Usage : python generators/normal_activity.py --profile config/profiles/zellige_bank_ma.yaml --days 7 --seed 1 --out data/generated/zellige --inject spray offhours_vpn
"""
from __future__ import annotations
import argparse
import csv
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

FIRST = ["amine", "salma", "youssef", "fatima", "karim", "nadia", "omar", "leila", "mehdi", "sara", "adama", "awa",
         "ibrahim", "mariam", "kofi", "aminata", "yao", "fanta", "moussa", "aicha", "brian", "grace", "peter", "mercy", "daniel", "faith"]
LAST = ["alaoui", "bennani", "tazi", "idrissi", "cherkaoui", "kone", "traore", "diallo", "coulibaly", "kouassi",
        "otieno", "mwangi", "kamau", "wanjiru", "odhiambo", "njoroge"]
UA = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4)",
      "Mozilla/5.0 (Linux; Android 13)", "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5)"]
PAGES = ["/", "/login", "/accueil", "/compte", "/api/v1/solde", "/api/v1/virements", "/aide", "/assets/app.js", "/assets/app.css"]
EXTERNAL_ATTACK_IPS = ["198.51.100.23", "203.0.113.77", "192.0.2.145"]   # plages de documentation (RFC 5737)
FOREIGN_VPN_IPS = {"RU": "198.51.100.88", "BR": "203.0.113.19"}


def users(domain: str, n: int, rng: random.Random) -> list[str]:
    names = set()
    while len(names) < n:
        names.add(f"{rng.choice(FIRST)}.{rng.choice(LAST)}")
    return sorted(names)


def work_time(day: datetime, hours: list[int], rng: random.Random) -> datetime:
    h = min(hours[1] - 0.01, max(hours[0], rng.gauss((hours[0] + hours[1]) / 2, (hours[1] - hours[0]) / 4)))
    return day.replace(hour=int(h), minute=int((h % 1) * 60), second=rng.randint(0, 59))


def syslog_ts(dt: datetime) -> str:
    return dt.strftime("%b %e %H:%M:%S")


def generate(profile: dict, days: int, seed: int, out: Path, inject: list[str], start: str = "2026-11-02") -> dict:
    rng = random.Random(seed)
    sim = profile["simulation"]
    tz = timezone(timedelta(hours=int(sim["timezone_offset"][:3])))
    base = datetime.fromisoformat(start).replace(tzinfo=tz)
    domain = profile["assets"]["domains"][0]
    team = users(domain, sim["employees"], rng)
    hosts = sim["hosts"]
    net = sim["internal_net"].split("/")[0].rsplit(".", 2)[0]   # "10.20"
    ip_of = {u: f"{net}.{rng.randint(1, 250)}.{rng.randint(2, 250)}" for u in team}
    events: list[tuple[datetime, str, str, dict]] = []  # (ts, stream, line, meta)

    for d in range(days):
        day = base + timedelta(days=d)
        weekend = day.weekday() >= 5
        for u in team:
            if weekend and rng.random() < 0.85:
                continue
            t0 = work_time(day, sim["work_hours"], rng)
            host = rng.choice(hosts)
            pid = rng.randint(1000, 60000)
            # connexions sshd (majorité par clé, quelques mots de passe, de rares fautes de frappe)
            if rng.random() < 0.35:
                if rng.random() < 0.06:
                    events.append((t0 - timedelta(seconds=20), "auth", f"{syslog_ts(t0 - timedelta(seconds=20))} {host} sshd[{pid}]: Failed password for {u} from {ip_of[u]} port {rng.randint(30000, 60000)} ssh2", {}))
                meth = rng.choice(["publickey", "publickey", "password"])
                events.append((t0, "auth", f"{syslog_ts(t0)} {host} sshd[{pid}]: Accepted {meth} for {u} from {ip_of[u]} port {rng.randint(30000, 60000)} ssh2", {}))
            # sudo + cron
            if rng.random() < 0.15:
                t1 = t0 + timedelta(minutes=rng.randint(1, 30))
                events.append((t1, "auth", f"{syslog_ts(t1)} {host} sudo: {u} : TTY=pts/0 ; PWD=/home/{u} ; USER=root ; COMMAND=/usr/bin/systemctl status app", {}))
            # VPN (pays habituels)
            if rng.random() < 0.5:
                cc = rng.choice(sim["usual_countries"])
                ip = f"41.{rng.randint(64, 250)}.{rng.randint(1, 250)}.{rng.randint(1, 250)}"
                events.append((t0 - timedelta(minutes=3), "vpn", f"{t0 - timedelta(minutes=3):%Y-%m-%dT%H:%M:%S%z} devname=vpn01 action=tunnel-up user={u} remip={ip} srccountry={cc}", {}))
            # Windows 4624/4625
            if rng.random() < 0.7:
                ev = 4625 if rng.random() < 0.03 else 4624
                events.append((t0, "win", json.dumps({"timestamp": t0.isoformat(), "EventID": ev, "TargetUserName": u,
                                                        "IpAddress": ip_of[u], "LogonType": rng.choice([2, 3, 10]), "Computer": rng.choice(hosts)}), {}))
            # web
            for _ in range(rng.randint(2, 8)):
                tw = t0 + timedelta(seconds=rng.randint(0, 6 * 3600))
                events.append((tw, "web", f'{ip_of[u]} - {u} [{tw:%d/%b/%Y:%H:%M:%S %z}] "GET {rng.choice(PAGES)} HTTP/1.1" {rng.choice([200] * 18 + [304, 404, 302])} {rng.randint(300, 40000)} "-" "{rng.choice(UA)}"', {}))
        # tâches planifiées
        for h in (2, 14):
            tc = day.replace(hour=h, minute=0, second=1)
            events.append((tc, "auth", f"{syslog_ts(tc)} {hosts[0]} CRON[{rng.randint(1000, 60000)}]: (root) CMD (/usr/local/bin/backup.sh)", {}))

    labels = []
    if "spray" in inject:  # 45 comptes testés par une IP externe en 9 minutes, puis un succès
        t = base + timedelta(days=min(2, days - 1), hours=sim["work_hours"][1] + 2, minutes=13)
        ip = EXTERNAL_ATTACK_IPS[0]
        targets = (team * 2)[:45]
        for i, u in enumerate(targets):
            ts = t + timedelta(seconds=12 * i)
            events.append((ts, "auth", f"{syslog_ts(ts)} {hosts[1]} sshd[{rng.randint(1000, 60000)}]: Failed password for invalid user {u} from {ip} port {rng.randint(30000, 60000)} ssh2", {"label": "spray_fail"}))
        ts = t + timedelta(seconds=12 * len(targets) + 30)
        events.append((ts, "auth", f"{syslog_ts(ts)} {hosts[1]} sshd[{rng.randint(1000, 60000)}]: Accepted password for {targets[7]} from {ip} port {rng.randint(30000, 60000)} ssh2", {"label": "spray_success"}))
    if "offhours_vpn" in inject:
        t = base + timedelta(days=min(3, days - 1), hours=3, minutes=12)
        victim = team[0]
        events.append((t, "vpn", f"{t:%Y-%m-%dT%H:%M:%S%z} devname=vpn01 action=tunnel-up user={victim} remip={FOREIGN_VPN_IPS['RU']} srccountry=RU", {"label": "offhours_vpn"}))

    events.sort(key=lambda e: e[0])
    out.mkdir(parents=True, exist_ok=True)
    files = {"auth": "auth.log", "vpn": "vpn.log", "web": "web_access.log", "win": "winevents.jsonl"}
    handles = {k: open(out / v, "w", encoding="utf-8") for k, v in files.items()}
    counts = {k: 0 for k in files}
    try:
        for ts, stream, line, meta in events:
            handles[stream].write(line + "\n")
            counts[stream] += 1
            if meta.get("label"):
                labels.append((files[stream], counts[stream], meta["label"]))
    finally:
        for h in handles.values():
            h.close()
    with open(out / "labels.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "line_no", "label"])
        w.writerows(labels)
    return {"profile": profile["id"], "seed": seed, "days": days, "users": len(team), "lines": counts, "labels": len(labels)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    ap.add_argument("--inject", nargs="*", default=[], choices=["spray", "offhours_vpn"])
    a = ap.parse_args(argv)
    with open(a.profile, encoding="utf-8") as f:
        profile = yaml.safe_load(f)
    if "simulation" not in profile:
        sys.exit("Le profil n'a pas de section 'simulation'")
    print(json.dumps(generate(profile, a.days, a.seed, Path(a.out), a.inject), ensure_ascii=False))


if __name__ == "__main__":
    main()
