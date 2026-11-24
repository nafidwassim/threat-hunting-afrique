# Zone SOC (Wazuh) - procédure de déploiement au laboratoire
1. `git clone https://github.com/wazuh/wazuh-docker.git -b v<VERSION_STABLE>` (vérifier la dernière version sur la page des releases).
2. `cd wazuh-docker/single-node && docker compose -f generate-indexer-certs.yml run --rm generator && docker compose up -d`
3. Changer les mots de passe par défaut immédiatement ; n'exposer aucun port hors du réseau du laboratoire.
4. Enrôler un agent par VM (Windows, Linux) ; copier `hunts/wazuh/*.xml` dans `/var/ossec/etc/rules/` ; tester avec `wazuh-logtest`.
5. Ingestion des journaux synthétiques : `localfile` (log_format syslog pour auth.log, json pour winevents.jsonl).
