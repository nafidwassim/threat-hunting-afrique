import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from generators import normal_activity
from thab.anomaly import VpnAnomalyModel, parse_vpn


def _prof():
    return yaml.safe_load((ROOT / "config/profiles/zellige_bank_ma.yaml").read_text(encoding="utf-8"))


def test_unseen_country_at_night_scores_above_normal_events(tmp_path):
    normal_activity.generate(_prof(), 14, 111, tmp_path / "tr", [])
    normal_activity.generate(_prof(), 14, 11, tmp_path / "te", ["offhours_vpn"])
    tr = parse_vpn((tmp_path / "tr/vpn.log").read_text(encoding="utf-8").splitlines())
    te = parse_vpn((tmp_path / "te/vpn.log").read_text(encoding="utf-8").splitlines())
    m = VpnAnomalyModel(seed=0).fit(tr)
    sc = m.score(te)
    attack = max(range(len(te)), key=lambda i: sc[i])
    assert te[attack]["country"] == "RU"


def test_model_is_deterministic(tmp_path):
    normal_activity.generate(_prof(), 7, 5, tmp_path / "a", [])
    ev = parse_vpn((tmp_path / "a/vpn.log").read_text(encoding="utf-8").splitlines())
    assert VpnAnomalyModel(seed=0).fit(ev).score(ev) == VpnAnomalyModel(seed=0).fit(ev).score(ev)


def test_llm_eval_harness_dry_run_counts_hallucinations():
    from hunts import llm_eval
    res = llm_eval.evaluate(ROOT / "config/profiles/zellige_bank_ma.yaml", 12, "mistral:7b", "http://localhost:11434", True)
    s = res["summary"]
    assert s["items"] == 12 and "SIMULATION" in s["model"]
    assert s["exploitable_rate"] == 1.0 and s["hallucinated_technique_rate"] > 0   # T9999 simulé rejeté
    assert all(r["verdict_analyste"] == "" for r in res["rows"])   # jamais de verdict pré-rempli
