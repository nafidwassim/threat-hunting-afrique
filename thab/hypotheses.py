"""Hypothèses de chasse ATT&CK : génération par règles (repli déterministe) et proposition par LLM local (Ollama).

Règle d'or du projet : toute sortie de l'IA est une HYPOTHÈSE CANDIDATE ; elle n'est jamais exécutée
ni partagée avant validation par un analyste (status = "candidate" -> "validated").
"""
from __future__ import annotations
import json
import re
from datetime import date

# Catégorie du renseignement -> techniques candidates (filtrées ensuite par le profil de menace).
CATEGORY_TTPS = {
    "ransomware": ["T1486", "T1490", "T1003", "T1021.001", "T1567", "T1078", "T1190"],
    "phishing_bec": ["T1566", "T1656", "T1657", "T1598", "T1583", "T1078"],
    "mobile_money_fraud": ["T1656", "T1657", "T1078", "T1199", "T1598"],
    "data_leak_sale": ["T1078", "T1110", "T1589", "T1650", "T1566", "T1567", "T1530"],
    "hacktivism_ddos": ["T1498", "T1499", "T1190", "T1567", "T1078"],
    "vuln_exploit": ["T1190", "T1133", "T1505.003", "T1078"],
}

TEMPLATES = {
    "data_leak_sale": "Des identifiants ou documents liés à {subject} circulent ; ils pourraient être réutilisés "
                      "(credential stuffing, phishing ciblé) contre {brands}.",
    "ransomware": "Un mode opératoire de rançongiciel décrit dans le renseignement pourrait viser {brands} "
                  "(accès initial puis chiffrement).",
    "phishing_bec": "Une campagne de phishing/BEC décrite pourrait cibler les clients ou employés de {brands}.",
    "mobile_money_fraud": "Une fraude mobile money / SIM swap décrite pourrait être reproduite contre {brands}.",
    "hacktivism_ddos": "Des revendications hacktivistes (DDoS, fuites) pourraient viser {brands}.",
    "vuln_exploit": "Une vulnérabilité exploitée activement pourrait toucher les équipements exposés de {brands}.",
}

# LOGIQUE de chasse par technique (pseudo-requêtes lisibles, NON exécutables telles quelles). Les requêtes exécutables
# (OpenSearch / règles Wazuh) sont dans hunts/wazuh/ et doivent être validées avec wazuh-logtest au laboratoire.
WAZUH_QUERIES = {
    "T1110": 'rule.groups:authentication_failed AND data.srcip:* | agg: cardinality(data.dstuser) by data.srcip, 10m >= 8',
    "T1110.003": 'rule.groups:authentication_failed | agg: cardinality(data.dstuser) by data.srcip, 10m >= 8',
    "T1110.004": 'rule.groups:authentication_failed | agg: count by data.srcip, 10m >= 20 AND rule.groups:authentication_success within 30m',
    "T1078": 'rule.groups:authentication_success AND NOT data.srcgeo.country_name:(<pays habituels du profil>) OR hour_of_day:[22 TO 5]',
    "T1486": 'data.win.eventdata.commandLine:(*vssadmin*delete*shadows* OR *wbadmin*delete*catalog*)',
    "T1490": 'data.win.eventdata.commandLine:(*vssadmin*delete*shadows* OR *bcdedit*recoveryenabled*no*)',
    "T1003": 'data.win.eventdata.targetImage:*lsass.exe AND data.win.system.eventID:10',
    "T1566": 'rule.groups:web AND data.url:(*<domaine typosquatté>*)',
    "T1583.001": 'data.dns.question.name:(<liste dnstwist>)',
    "T1190": 'rule.groups:web AND (rule.level:>=10 OR data.protocol:POST AND data.id:(500 OR 200) AND data.url:(*.php OR *.aspx))',
    "T1133": 'rule.groups:(vpn OR sshd) AND rule.groups:authentication_success',
    "T1656": 'data.app.action:"sim_swap" | agg: count by data.app.agent_id, 1h >= 5',
    "T1657": 'data.app.action:("beneficiary_change" OR "transfer") | séquence: changement bénéficiaire puis virement > seuil en 24h',
    "T1498": 'rule.groups:firewall | agg: count by data.srcip, 1m >= 1000',
    "T1567": 'data.network.bytes_out:>500000000 AND NOT data.dstip:(<plages autorisées>)',
}


def _filter_techniques(category: str, tp: dict) -> list[dict]:
    cand = CATEGORY_TTPS.get(category, [])
    by_id = {t["id"]: t for t in tp["ttps"]}
    out = []
    for tid in cand:
        key = tid if tid in by_id else tid.split(".")[0]
        if key in by_id:
            out.append(by_id[key] | {"id": tid})
    out.sort(key=lambda t: -t["weight"])
    return out


def propose_rules(item: dict, profile: dict, tp: dict, today: date | None = None, top: int = 3) -> dict:
    cat = item["category"]
    if cat not in TEMPLATES:
        raise ValueError(f"Aucune hypothèse pour la catégorie {cat!r}")
    techs = _filter_techniques(cat, tp)[:top]
    brands = " / ".join(profile["assets"]["brands"])
    queries = {t["id"]: WAZUH_QUERIES.get(t["id"]) or WAZUH_QUERIES.get(t["id"].split(".")[0]) for t in techs}
    return {
        "hypothesis_id": f"H-{item['id']}-{profile['id']}",
        "item_id": item["id"],
        "statement": TEMPLATES[cat].format(subject=item.get("subject", "l'entité mentionnée"), brands=brands),
        "techniques": [{"id": t["id"], "name": t["name"], "tactic": t["tactic"], "weight": t["weight"]} for t in techs],
        "wazuh_queries": {k: v for k, v in queries.items() if v},
        "queries_status": "pseudo-requêtes (logique de chasse) à traduire et valider au laboratoire ; versions exécutables : hunts/wazuh/",
        "generated_by": "rules",
        "status": "candidate",           # doit être validée par un analyste
        "date": (today or date.today()).isoformat(),
    }


def build_llm_prompt(item: dict, profile: dict, allowed_ids: list[str]) -> str:
    return (
        "Tu es un analyste CTI. Réponds UNIQUEMENT par un JSON valide de la forme "
        '{"hypothesis": "...", "techniques": ["Txxxx", ...], "rationale": "..."}.\n'
        f"Entreprise : {profile['name']} ; secteur : {profile['sector']} ; pays : {profile['country']} ; "
        f"technologies : {', '.join(profile.get('technologies', []))}.\n"
        f"Techniques ATT&CK autorisées (n'en invente aucune autre) : {', '.join(allowed_ids)}.\n"
        f"Renseignement : {item['text']}\n"
        "Formule une hypothèse de chasse vérifiable dans les journaux du SIEM, en maximum 3 techniques."
    )


def propose_llm(item: dict, profile: dict, tp: dict, model: str = "mistral:7b",
                host: str = "http://localhost:11434", timeout: int = 120, _post=None) -> dict | None:
    """Interroge un LLM local via Ollama. Retourne None si le serveur est injoignable ou la sortie invalide.
    Les identifiants de technique hors liste autorisée sont rejetés (garde-fou anti-hallucination)."""
    allowed = [t["id"] for t in _filter_techniques(item["category"], tp)] or [t["id"] for t in tp["ttps"][:10]]
    prompt = build_llm_prompt(item, profile, allowed)
    try:
        if _post is None:
            import requests
            _post = lambda url, payload: requests.post(url, json=payload, timeout=timeout).json()
        raw = _post(f"{host}/api/generate", {"model": model, "prompt": prompt, "stream": False, "format": "json",
                                              "options": {"temperature": 0.2}})
        data = json.loads(raw["response"])
    except Exception:
        return None
    techs = [t for t in data.get("techniques", []) if isinstance(t, str) and re.fullmatch(r"T\d{4}(\.\d{3})?", t)]
    rejected = [t for t in techs if t not in allowed]
    techs = [t for t in techs if t in allowed][:3]
    if not data.get("hypothesis") or not techs:
        return None
    return {"hypothesis_id": f"HL-{item['id']}-{profile['id']}", "item_id": item["id"],
            "statement": str(data["hypothesis"])[:500], "techniques": techs, "rationale": str(data.get("rationale", ""))[:500],
            "rejected_techniques": rejected, "generated_by": f"llm:{model}", "status": "candidate"}
