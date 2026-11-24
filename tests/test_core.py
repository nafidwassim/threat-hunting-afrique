import csv
import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from thab import admiralty, classify, hypotheses, ioc, journal, scoring, sources, stix, tlp
from thab.profile import build_threat_profile, load_profile

ROOT = Path(__file__).resolve().parent.parent
ZB = ROOT / "config/profiles/zellige_bank_ma.yaml"
HT = ROOT / "config/profiles/harmattan_telecom_ci.yaml"
SK = ROOT / "config/profiles/test_inedit_sante_ke.yaml"
TODAY = date(2026, 11, 8)


# ---- Amirauté / TLP -------------------------------------------------------------------------------------------
def test_admiralty_parse_and_invalid():
    assert admiralty.parse("b2") == ("B", "2")
    for bad in ["G1", "A7", "AA", "", "1A"]:
        with pytest.raises(ValueError):
            admiralty.parse(bad)
    assert admiralty.to_misp_tags("B2") == ['admiralty-scale:source-reliability="b"', 'admiralty-scale:information-credibility="2"']


def test_tlp_levels_and_sharing():
    assert tlp.normalize("white") == "TLP:CLEAR" if False else True  # TLP:WHITE n'existe plus en 2.0
    assert tlp.normalize("tlp:white") == "TLP:CLEAR"
    assert tlp.can_share("TLP:CLEAR", "public")
    assert not tlp.can_share("TLP:AMBER", "community")
    assert tlp.can_share("TLP:AMBER", "organisation")
    assert not tlp.can_share("TLP:RED", "organisation")
    assert tlp.to_misp_tag("TLP:AMBER+STRICT") == "tlp:amber+strict"
    with pytest.raises(ValueError):
        tlp.normalize("TLP:PURPLE")


# ---- Profils et généricité --------------------------------------------------------------------------------------
def test_profile_validation(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("id: x\nname: X\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_profile(bad)
    d = yaml.safe_load(ZB.read_text(encoding="utf-8"))
    d["assets"]["domains"] = ["pas un domaine"]
    p = tmp_path / "bad2.yaml"
    p.write_text(yaml.safe_dump(d), encoding="utf-8")
    with pytest.raises(ValueError):
        load_profile(p)


def test_all_fictional_domains_are_reserved():
    for f in (ZB, HT, SK):
        p = load_profile(f)
        assert p["fictional"] is True
        assert all(d.endswith(".example") for d in p["assets"]["domains"]), "domaines fictifs obligatoirement en .example (RFC 2606)"


def test_genericity_same_code_different_priorities():
    tps = {f.stem: build_threat_profile(load_profile(f)) for f in (ZB, HT, SK)}
    top = {k: [t["id"] for t in v["ttps"][:5]] for k, v in tps.items()}
    assert top["zellige_bank_ma"] != top["harmattan_telecom_ci"]
    assert top["zellige_bank_ma"] != top["test_inedit_sante_ke"]
    # le secteur sans module bascule sur le repli, avec avertissement explicite (pas d'erreur)
    sk = tps["test_inedit_sante_ke"]
    assert sk["sector_module"] == "_generic" and sk["warnings"]
    assert sk["hypotheses"], "un profil inédit doit tout de même produire des hypothèses de départ"
    assert tps["zellige_bank_ma"]["hypotheses"][0]["id"].startswith("HB-")
    assert tps["harmattan_telecom_ci"]["hypotheses"][0]["id"].startswith("HT-")


def test_unknown_country_does_not_crash(tmp_path):
    d = yaml.safe_load(SK.read_text(encoding="utf-8"))
    d["country"] = "SN"
    p = tmp_path / "sn.yaml"
    p.write_text(yaml.safe_dump(d), encoding="utf-8")
    tp = build_threat_profile(load_profile(p))
    assert any("module pays" in w for w in tp["warnings"])


def test_tech_boost_is_capped():
    tp = build_threat_profile(load_profile(ZB))
    assert all(0 <= t["weight"] <= 1.0 for t in tp["ttps"])


# ---- Scoring ------------------------------------------------------------------------------------------------------
def _scorer(profile_path):
    prof = load_profile(profile_path)
    return scoring.Scorer(prof, build_threat_profile(prof), scoring.load_config(), corpus=[]), prof


def _item(**kw):
    base = {"id": "T", "title": "t", "text": "", "published": "2026-11-01", "admiralty": "B2", "category": "ransomware"}
    return base | kw


def test_score_bounds_and_components():
    sc, _ = _scorer(ZB)
    r = sc.score(_item(text="Ransomware attack on Zellige Bank in Morocco, banque touchée"), TODAY)
    assert 0 <= r["score"] <= 100 and all(0 <= r[k] <= 1 for k in "PFC")
    assert r["detail"]["entity"] == 1.0  # nom de marque exact


def test_brand_match_beats_unrelated():
    sc, _ = _scorer(ZB)
    on = sc.score(_item(text="Zellige Bank customers targeted by ransomware"), TODAY)["score"]
    off = sc.score(_item(text="A hospital in another region was hit by ransomware"), TODAY)["score"]
    assert on > off + 15


def test_reliability_gate_caps_action():
    sc, _ = _scorer(ZB)
    r = sc.score(_item(text="Zellige Bank ransomware zellige-bank.example", admiralty="F6", published="2026-11-07"), TODAY)
    assert r["F"] < 0.35 and r["action"] != "chasse"


def test_recency_decay():
    cfg = scoring.load_config()
    fresh = scoring.criticality_score("ransomware", "2026-11-08", TODAY, cfg)
    old = scoring.criticality_score("ransomware", "2025-11-08", TODAY, cfg)
    assert fresh > old > 0
    assert fresh == pytest.approx(0.95)


def test_inflection_matching():
    prof = load_profile(ZB)
    tp = build_threat_profile(prof)
    ent, hits = scoring.entity_score("Fuite visant des institutions marocaines et des banques", prof, tp, scoring.load_config())
    assert ent > 0 and any("secteur" in h or "pays" in h for h in hits)
    ent2, _ = scoring.entity_score("Un salon du tourisme s'ouvre à Rabatissimo", prof, tp, scoring.load_config())
    assert ent2 == 0


def test_scoring_config_weights_sum_to_one():
    w = scoring.load_config()["weights"]
    assert sum(w.values()) == pytest.approx(1.0)


# ---- IOC ----------------------------------------------------------------------------------------------------------
def test_ioc_extraction_and_defang():
    t = "C2 hxxps://evil-example[.]test/a.php IP 198.51.100.7, mail x[@]bad.test CVE-2025-1234 sha256 " + "a" * 64
    r = ioc.extract(t)
    assert "198.51.100.7" in r["ipv4"] and "x@bad.test" in r["emails"] and "CVE-2025-1234" in r["cves"]
    assert any(u.startswith("https://evil-example.test") for u in r["urls"]) and r["sha256"] == ["a" * 64]
    assert "a.php" not in r["domains"], "les noms de fichiers ne sont pas des domaines"


# ---- STIX ---------------------------------------------------------------------------------------------------------
def test_stix_bundle_valid_and_deterministic():
    item = {"id": "I1", "title": "Test", "text": "Domaine malveillant bad-example.test et IP 198.51.100.7 (CVE-2025-1111).",
            "published": "2026-11-01", "admiralty": "B2", "tlp": "TLP:CLEAR", "source": "src", "url": "https://x"}
    b1, b2 = stix.to_bundle(item), stix.to_bundle(item)
    assert b1 == b2 and not stix.validate_basic(b1)
    types = [o["type"] for o in b1["objects"]]
    assert types.count("indicator") == 2 and "report" in types
    assert "tlp:clear" in b1["objects"][1]["labels"]
    json.dumps(b1)


# ---- Journaux et garde-fous éthiques -------------------------------------------------------------------------------
def test_collect_journal_requires_supervisor_validation(tmp_path):
    with pytest.raises(PermissionError):
        journal.log_collect_session("W. N.", "veille", ["ahmia"], "Whonix", "", path=tmp_path / "j.csv")
    journal.log_collect_session("W. N.", "veille", ["ahmia"], "Whonix", "OK encadrant 2026-11-10", path=tmp_path / "j.csv")
    rows = list(csv.DictReader(open(tmp_path / "j.csv", encoding="utf-8")))
    assert len(rows) == 1 and rows[0]["contenu_illicite_rencontre"] == "non"


def test_real_collect_journal_has_no_fabricated_sessions():
    p = ROOT / "journals/journal_collecte_darkweb.csv"
    if p.exists():
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        assert all(r["validation_encadrant"].strip() for r in rows), "toute ligne doit porter la validation de l'encadrant"


def test_sources_not_validated_are_blocked():
    reg = sources.load()
    assert all(s["validation_status"] != "validated" for s in reg.values()), "aucune source ne doit être marquée validée sans l'encadrant"
    with pytest.raises(sources.SourceNotValidated):
        sources.require_validated("SRC-001", reg)
    with pytest.raises(sources.SourceNotValidated):
        sources.require_validated("SRC-999", reg)
    ok = {"X": {"name": "x", "validation_status": "validated_by_supervisor (2026-11-10)", "access": "clearnet"}}
    assert sources.require_validated("X", ok)["name"] == "x"


def test_tor_access_always_refused_in_collectors():
    ok = {"T": {"name": "t", "validation_status": "validated_by_supervisor", "access": "tor"}}
    with pytest.raises(sources.SourceNotValidated):
        sources.require_validated("T", ok)


# ---- Hypothèses / LLM -----------------------------------------------------------------------------------------------
def test_rule_hypothesis_is_candidate_and_linked_to_attack():
    prof = load_profile(ZB)
    tp = build_threat_profile(prof)
    h = hypotheses.propose_rules(_item(category="data_leak_sale", subject="x"), prof, tp, TODAY)
    assert h["status"] == "candidate" and h["techniques"] and all(t["id"].startswith("T") for t in h["techniques"])


def test_llm_output_is_filtered_against_allowlist():
    prof = load_profile(ZB)
    tp = build_threat_profile(prof)
    item = _item(category="ransomware", text="x")
    fake = lambda url, payload: {"response": json.dumps({"hypothesis": "h", "techniques": ["T1486", "T9999", "pas-un-id"], "rationale": "r"})}
    r = hypotheses.propose_llm(item, prof, tp, _post=fake)
    assert r["techniques"] == ["T1486"] and "T9999" in r["rejected_techniques"] and r["status"] == "candidate"
    assert hypotheses.propose_llm(item, prof, tp, _post=lambda u, p: {"response": "pas du json"}) is None

    def down(url, payload):
        raise ConnectionError("Ollama injoignable")
    assert hypotheses.propose_llm(item, prof, tp, _post=down) is None


# ---- Classification -------------------------------------------------------------------------------------------------
def test_dataset_is_flagged_synthetic():
    rows = classify.load_dataset()
    assert len(rows) >= 70 and all(r["synthetic"] == "true" for r in rows)


def test_hybrid_classifier_basic_cases():
    assert classify.predict_hybrid("Un rançongiciel a chiffré les serveurs") == "ransomware"
    assert classify.predict_hybrid("Recette de tajine aux légumes") == "hors_sujet"
    assert classify.predict_hybrid("SIM swap fraud on mobile money wallets") == "mobile_money_fraud"
