"""Évaluation du LLM local (Ollama) pour les hypothèses de chasse.
Compare, sur N renseignements annotés, la sortie du LLM aux hypothèses par règles :
  - taux de réponses exploitables (JSON valide + au moins une technique autorisée)
  - taux de techniques hallucinées (hors liste autorisée, rejetées par le garde-fou)
  - accord avec les règles (Jaccard moyen des techniques) -> repère, pas vérité terrain
  - revue humaine : colonne vide `verdict_analyste` (pertinente / partielle / fausse) à remplir par un analyste
Usage : python hunts/llm_eval.py --profile config/profiles/zellige_bank_ma.yaml --n 20 [--model mistral:7b]
        python hunts/llm_eval.py ... --dry-run   (réponses simulées : valide seulement le banc, PAS le modèle)
Sortie : data/generated/llm_eval_<profil>.json et .csv (pour la relecture analyste)."""
from __future__ import annotations
import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from thab import classify, hypotheses
from thab.profile import build_threat_profile, load_profile

SKIP = {"hors_sujet"}


def pick_items(n: int) -> list[dict]:
    rows = [r for r in classify.load_dataset() if r["category"] not in SKIP and r["category"] in hypotheses.TEMPLATES]
    by_cat: dict[str, list[dict]] = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    out, i = [], 0
    while len(out) < min(n, len(rows)):   # tirage équilibré par catégorie, déterministe
        for cat in sorted(by_cat):
            if i < len(by_cat[cat]) and len(out) < n:
                out.append(by_cat[cat][i])
        i += 1
    return out


def _dry_post(url, payload):
    allowed = payload["prompt"].split("n'en invente aucune autre) : ")[1].split("\n")[0].split(", ")
    return {"response": json.dumps({"hypothesis": "Hypothèse simulée.", "techniques": allowed[:2] + ["T9999"], "rationale": "simulation"})}


def evaluate(profile_path: Path, n: int, model: str, host: str, dry: bool) -> dict:
    prof = load_profile(profile_path)
    tp = build_threat_profile(prof)
    items = pick_items(n)
    rows, ok, halluc, techs_total, jacc = [], 0, 0, 0, []
    for it in items:
        item = {"id": it["id"], "title": it.get("title", ""), "text": it["text"], "category": it["category"], "subject": it.get("title", "")}
        rule = hypotheses.propose_rules(item, prof, tp, date.today())
        rset = {t["id"] for t in rule["techniques"]}
        res = hypotheses.propose_llm(item, prof, tp, model=model, host=host, _post=_dry_post if dry else None)
        if res:
            ok += 1
            lset = set(res["techniques"])
            halluc += len(res["rejected_techniques"])
            techs_total += len(res["techniques"]) + len(res["rejected_techniques"])
            jacc.append(len(lset & rset) / len(lset | rset) if lset | rset else 0.0)
        rows.append({"item_id": it["id"], "category": it["category"], "rule_techniques": " ".join(sorted(rset)),
                     "llm_techniques": " ".join(res["techniques"]) if res else "", "llm_rejected": " ".join(res["rejected_techniques"]) if res else "",
                     "llm_statement": res["statement"] if res else "(sortie inexploitable)", "verdict_analyste": ""})
    summary = {"profile": prof["id"], "model": "SIMULATION (dry-run)" if dry else model, "items": len(items),
               "exploitable_rate": round(ok / len(items), 3) if items else 0.0,
               "hallucinated_technique_rate": round(halluc / techs_total, 3) if techs_total else 0.0,
               "mean_jaccard_vs_rules": round(sum(jacc) / len(jacc), 3) if jacc else 0.0,
               "human_review": "à faire : remplir verdict_analyste dans le CSV (au moins 2 relecteurs pour mesurer l'accord)"}
    return {"summary": summary, "rows": rows}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--model", default="mistral:7b")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    res = evaluate(Path(a.profile), a.n, a.model, a.host, a.dry_run)
    stem = Path(a.profile).stem + ("_dryrun" if a.dry_run else "")
    out = ROOT / "data/generated"
    (out / f"llm_eval_{stem}.json").write_text(json.dumps(res["summary"], indent=2, ensure_ascii=False), encoding="utf-8")
    with open(out / f"llm_eval_{stem}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(res["rows"][0]))
        w.writeheader()
        w.writerows(res["rows"])
    print(json.dumps(res["summary"], indent=2, ensure_ascii=False))
