"""Premier test de généricité : mêmes code et configuration, 3 profils dont un secteur SANS module (santé).
Vérifie que les priorités et hypothèses diffèrent d'un profil à l'autre sans modifier le code."""
import json
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from thab.profile import build_threat_profile, load_profile

PROFILES = ["zellige_bank_ma", "harmattan_telecom_ci", "test_inedit_sante_ke"]


def jaccard(a, b):
    a, b = set(a), set(b)
    return round(len(a & b) / len(a | b), 3)


def main():
    res = {}
    for pf in PROFILES:
        p = load_profile(ROOT / f"config/profiles/{pf}.yaml")
        tp = build_threat_profile(p)
        res[pf] = {"sector_module": tp["sector_module"], "country_module": tp["country_module"], "warnings": tp["warnings"],
                   "top10_ttps": [t["id"] for t in tp["ttps"][:10]], "top5_weights": [(t["id"], t["weight"]) for t in tp["ttps"][:5]],
                   "hypotheses": [h["id"] for h in tp["hypotheses"]], "n_keywords": len(tp["keywords"]),
                   "context": [c["tendency"] for c in tp["country_context"]]}
    sim = {f"{a} vs {b}": {"jaccard_top10_ttps": jaccard(res[a]["top10_ttps"], res[b]["top10_ttps"]),
                           "jaccard_hypotheses": jaccard(res[a]["hypotheses"], res[b]["hypotheses"])} for a, b in combinations(PROFILES, 2)}
    out = {"profils": res, "similarite": sim}
    (ROOT / "data/generated/genericity_test.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
