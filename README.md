# Threat Hunting Afrique (projet 3pH, HESTIM 5A) - dépôt mi-parcours
Entreprises 100 % fictives (domaines .example). Aucune donnée réelle, aucune collecte dark web directe à ce jour.
- `config/` profils, modules sectoriels/pays, scoring, registre des sources
- `thab/` profil de menace, scoring, Amirauté, TLP, STIX, hypothèses, collecteurs (garde-fou : sources validées)
- `generators/` journaux et fuite d'identifiants synthétiques ; `hunts/` hypothèses et chasses Wazuh
- `scripts/go_nogo_challenge.py`, `scripts/genericity_test.py` ; `journals/` ; `infra/` (non déployé)
Tests : `python -m pytest -q` (34 tests). Anomalies : `python hunts/anomaly_eval.py` ; évaluation LLM : `python hunts/llm_eval.py --profile ... --n 20`. Statut honnête : voir le rapport, chapitre « État d'avancement ».
