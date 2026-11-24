"""Jeu de fuite d'identifiants SIMULÉ (exigence : aucune donnée personnelle réelle).

Génère des comptes fictifs @<domaine>.example avec des "hachages" aléatoires sans lien avec un vrai mot de passe,
et la liste CDB Wazuh (format `clé:valeur`) correspondante, utilisée par l'hypothèse « comptes valides issus d'une fuite ».
Usage : python generators/credential_leak.py --profile config/profiles/zellige_bank_ma.yaml --n 200 --seed 1 --out data/generated/zellige
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import random
from pathlib import Path

import yaml

FIRST = ["amine", "salma", "youssef", "fatima", "karim", "nadia", "omar", "leila", "adama", "awa", "ibrahim", "mariam", "kofi", "brian", "grace"]
LAST = ["alaoui", "bennani", "tazi", "kone", "traore", "diallo", "kouassi", "otieno", "mwangi", "kamau"]


def generate(profile: dict, n: int, seed: int, out: Path) -> dict:
    rng = random.Random(seed)
    domain = profile["assets"]["domains"][0]
    out.mkdir(parents=True, exist_ok=True)
    rows = set()
    while len(rows) < n:
        rows.add(f"{rng.choice(FIRST)}.{rng.choice(LAST)}{rng.randint(1, 99) if rng.random() < .5 else ''}@{domain}")
    rows = sorted(rows)
    with open(out / "leak_simulated.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["email", "password_hash_sha256", "source", "synthetic"])
        for e in rows:
            fake = hashlib.sha256(f"{seed}:{e}:{rng.random()}".encode()).hexdigest()
            w.writerow([e, fake, "simulated-leak", "true"])
    with open(out / "leaked_accounts.cdb", "w", encoding="utf-8") as f:
        for e in rows:
            f.write(f"{e.split('@')[0]}:leak-simulated\n")      # clé = nom d'utilisateur
    return {"profile": profile["id"], "accounts": len(rows), "domain": domain}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    print(generate(yaml.safe_load(open(a.profile, encoding="utf-8")), a.n, a.seed, Path(a.out)))
