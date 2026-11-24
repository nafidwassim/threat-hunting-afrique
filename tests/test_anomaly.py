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
