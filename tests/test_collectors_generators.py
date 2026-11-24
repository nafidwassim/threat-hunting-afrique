import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from thab import sources
from thab.collectors import crtsh, internetdb, rss, telegram_public, typosquat
from generators import credential_leak, normal_activity
from hunts import offline_eval


def test_crtsh_parse_and_new_names():
    sample = json.dumps([
        {"id": 1, "name_value": "www.zellige-bank.example\nmail.zellige-bank.example", "issuer_name": "CA", "not_before": "2026-11-01T00:00:00"},
        {"id": 2, "name_value": "*.zellige-bank.example", "issuer_name": "CA", "not_before": "2026-11-02T00:00:00"},
        {"id": 3, "name_value": "vpn-test.zellige-bank.example", "issuer_name": "CA", "not_before": "2026-11-03T00:00:00"},
    ])
    rows = crtsh.parse(sample)
    names = {r["name"] for r in rows}
    assert {"www.zellige-bank.example", "mail.zellige-bank.example", "zellige-bank.example", "vpn-test.zellige-bank.example"} == names
    assert [r["name"] for r in crtsh.new_names(rows, {"www.zellige-bank.example", "mail.zellige-bank.example", "zellige-bank.example"})] == ["vpn-test.zellige-bank.example"]
    assert crtsh.parse("") == []


def test_internetdb_summary():
    s = internetdb.summarize({"ip": "198.51.100.5", "ports": [443, 3389, 22], "vulns": ["CVE-2024-0001"], "hostnames": [], "tags": []})
    assert s["priority"] == "haute" and s["risky_ports"] == {3389: "rdp"}
    assert internetdb.summarize({"ip": "198.51.100.6", "ports": [443]})["priority"] == "normale"


def test_typosquat_permutations():
    p = typosquat.permutations("zellige-bank.example")
    assert "zellige-bank.com" in p and "login-zellige-bank.example" in p and "zellige-bank.example" not in p
    assert all(".." not in d and not d.startswith("-") for d in p)
    assert len(p) > 50


def test_rss_parse_and_xxe_refused():
    rssx = """<rss><channel><item><title>T1</title><link>https://a</link><pubDate>Mon, 02 Nov 2026 10:00:00 +0000</pubDate><description>d</description></item></channel></rss>"""
    r = rss.parse(rssx)
    assert r[0]["title"] == "T1" and r[0]["published"] == "2026-11-02"
    evil = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><rss><channel><item><title>&a;</title></item></channel></rss>'
    with pytest.raises(ValueError):
        rss.parse(evil)


def test_telegram_parse_and_fetch_blocked():
    html = ('<div class="tgme_widget_message"><a class="tgme_widget_message_date" href="https://t.me/x/1"><time datetime="2026-11-01T10:00:00+00:00"></time></a>'
            '<div class="tgme_widget_message_text">Fuite   revendiquée\n sur un canal</div></div>')
    m = telegram_public.parse(html)
    assert m and m[0]["text"] == "Fuite revendiquée sur un canal" and m[0]["url"] == "https://t.me/x/1"
    with pytest.raises(sources.SourceNotValidated):
        telegram_public.fetch("un_canal")  # SRC-008 non validée : aucune requête réseau ne doit partir


def test_generators_are_deterministic_and_synthetic(tmp_path):
    prof = yaml.safe_load((ROOT / "config/profiles/zellige_bank_ma.yaml").read_text(encoding="utf-8"))
    a = normal_activity.generate(prof, 3, 7, tmp_path / "a", ["spray"])
    b = normal_activity.generate(prof, 3, 7, tmp_path / "b", ["spray"])
    assert a == b
    assert (tmp_path / "a/auth.log").read_text() == (tmp_path / "b/auth.log").read_text()
    c = normal_activity.generate(prof, 3, 8, tmp_path / "c", [])
    assert (tmp_path / "a/auth.log").read_text() != (tmp_path / "c/auth.log").read_text()
    leak = credential_leak.generate(prof, 50, 1, tmp_path / "l")
    text = (tmp_path / "l/leak_simulated.csv").read_text()
    assert leak["accounts"] == 50 and "@zellige-bank.example" in text and "true" in text
    assert all("@" not in l.split(":")[0] for l in (tmp_path / "l/leaked_accounts.cdb").read_text().splitlines())


def test_offline_hunts_detect_injected_attacks_and_baseline_is_quiet(tmp_path):
    prof = yaml.safe_load((ROOT / "config/profiles/harmattan_telecom_ci.yaml").read_text(encoding="utf-8"))
    normal_activity.generate(prof, 7, 3, tmp_path / "atk", ["spray", "offhours_vpn"])
    res = offline_eval.evaluate(tmp_path / "atk", prof)
    assert res["HB-01_password_spraying"]["recall"] == 1.0 and res["HB-03_vpn_hors_profil"]["recall"] == 1.0
    normal_activity.generate(prof, 7, 3, tmp_path / "clean", [])
    auth = (tmp_path / "clean/auth.log").read_text().splitlines()
    assert offline_eval.detect_spray(auth) == [], "aucune fausse alerte attendue sur l'activité normale"


def test_no_real_personal_data_in_generated_files():
    for d in (ROOT / "data/generated").glob("*/"):
        for f in d.glob("*.csv"):
            if f.name == "leak_simulated.csv":
                assert all(".example" in line for line in f.read_text().splitlines()[1:])
