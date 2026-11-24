"""Défi Go/NoGo : pour chaque renseignement réel -> source, cotation, TLP, catégorie, score par profil, hypothèse, bundle STIX.
Usage : python scripts/go_nogo_challenge.py  (écrit data/generated/go_nogo_challenge/)"""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from thab import admiralty, classify, hypotheses, ioc, stix, tlp
from thab.profile import build_threat_profile, load_profile
from thab.scoring import Scorer, load_config

TODAY = date(2026, 11, 8)
PROFILES = ["zellige_bank_ma", "harmattan_telecom_ci", "test_inedit_sante_ke"]


def main():
    items = json.loads((ROOT / "data/intel/go_nogo_items.json").read_text(encoding="utf-8"))
    cfg = load_config()
    model = classify.train()
    corpus = [r["title"] + ". " + r["text"] for r in classify.load_dataset()] + [i["text"] for i in items]
    out_dir = ROOT / "data/generated/go_nogo_challenge"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for it in items:
        it["category"] = classify.predict_hybrid(it["title"] + ". " + it["text"], model)
        row = {"id": it["id"], "title": it["title"], "source": it["source"], "url": it["url"], "published": it["published"],
               "cotation": it["admiralty"], "cotation_label": admiralty.label(it["admiralty"]), "tlp": tlp.normalize(it["tlp"]),
               "category_predicted": it["category"], "iocs": {k: v for k, v in ioc.extract(it["text"]).items() if v}, "profiles": {}}
        for pf in PROFILES:
            prof = load_profile(ROOT / f"config/profiles/{pf}.yaml")
            tp = build_threat_profile(prof)
            sc = Scorer(prof, tp, cfg, corpus).score(it, TODAY)
            entry = {"score": sc["score"], "action": sc["action"], "P": sc["P"], "F": sc["F"], "C": sc["C"], "hits": sc["detail"]["hits"]}
            if sc["action"] in ("chasse", "surveillance"):
                h = hypotheses.propose_rules(it, prof, tp, TODAY)
                entry["hypothesis"] = h
                bundle = stix.to_bundle(it, sc, h)
                errs = stix.validate_basic(bundle)
                entry["stix_errors"] = errs
                (out_dir / f"{it['id']}__{pf}.stix.json").write_text(stix.dumps(bundle), encoding="utf-8")
            row["profiles"][pf] = entry
        results.append(row)
    (out_dir / "challenge_results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    for r in results:
        print(f"\n{r['id']} [{r['category_predicted']}] {r['cotation']} {r['tlp']}")
        for pf, e in r["profiles"].items():
            h = e.get("hypothesis")
            print(f"  {pf:<24} score={e['score']:<5} {e['action']:<12} P={e['P']} F={e['F']} C={e['C']} hits={e['hits']}"
                  + (f" | {h['hypothesis_id']} {[t['id'] for t in h['techniques']]}" if h else ""))


if __name__ == "__main__":
    main()
