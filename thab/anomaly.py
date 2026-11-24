"""Détection d'anomalies non supervisée (Isolation Forest) sur les connexions VPN.

Complète les règles déterministes de hunts/ : aucune liste de pays ni d'horaires n'est codée en dur ;
le modèle apprend la « normale » d'une entreprise à partir de son propre historique (apprentissage sur logs sains),
ce qui garde le modèle générique. Sortie = HYPOTHÈSES à vérifier par l'analyste, jamais une alerte validée.
"""
from __future__ import annotations
import math
import re
from collections import Counter
from datetime import datetime

import numpy as np
from sklearn.ensemble import IsolationForest

RE_VPN = re.compile(r"^(\S+) devname=\S+ action=tunnel-up user=(\S+) remip=(\S+) srccountry=(\w+)")


def parse_vpn(lines: list[str]) -> list[dict]:
    out = []
    for no, line in enumerate(lines, 1):
        m = RE_VPN.match(line)
        if m:
            ts = datetime.strptime(m.group(1)[:19], "%Y-%m-%dT%H:%M:%S")
            out.append({"line": no, "ts": ts, "user": m.group(2), "country": m.group(4)})
    return out


class VpnAnomalyModel:
    """Variables : heure (sin/cos), week-end, rareté du pays, pays jamais vu pour l'utilisateur, écart horaire.

    Limite connue d'Isolation Forest : une valeur hors de la plage vue à l'apprentissage n'est pas isolée plus vite.
    Pour que les variables de nouveauté varient aussi à l'apprentissage, elles sont calculées de façon SÉQUENTIELLE
    (chaque événement d'entraînement est décrit par l'historique qui le précède), comme en production."""

    def __init__(self, contamination: float = 0.01, seed: int = 0):
        self.iforest = IsolationForest(n_estimators=300, contamination=contamination, random_state=seed)
        self.country_freq: Counter = Counter()
        self.user_countries: dict[str, set[str]] = {}
        self.hours_seen: Counter = Counter()
        self.n = 0

    def _features(self, ev: dict) -> list[float]:
        h = ev["ts"].hour + ev["ts"].minute / 60
        rarity = -math.log((self.country_freq.get(ev["country"], 0) + 1) / (self.n + 2))
        new_for_user = 0.0 if ev["country"] in self.user_countries.get(ev["user"], set()) else 1.0
        gap = min((min(abs(h - k), 24 - abs(h - k)) for k in self.hours_seen), default=0.0)
        return [math.sin(2 * math.pi * h / 24), math.cos(2 * math.pi * h / 24),
                float(ev["ts"].weekday() >= 5), rarity, new_for_user, gap]

    def _update(self, ev: dict) -> None:
        self.country_freq[ev["country"]] += 1
        self.n += 1
        self.user_countries.setdefault(ev["user"], set()).add(ev["country"])
        self.hours_seen[ev["ts"].hour] += 1

    def fit(self, events: list[dict]) -> "VpnAnomalyModel":
        feats = []
        for e in sorted(events, key=lambda e: e["ts"]):
            feats.append(self._features(e))   # historique antérieur seulement
            self._update(e)
        self.iforest.fit(np.array(feats))
        return self

    def score(self, events: list[dict]) -> list[float]:
        """Plus le score est élevé, plus l'événement est atypique."""
        return list((-self.iforest.score_samples(np.array([self._features(e) for e in events]))))

    def predict(self, events: list[dict]) -> list[bool]:
        return [p == -1 for p in self.iforest.predict(np.array([self._features(e) for e in events]))]
