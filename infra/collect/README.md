# Zone de collecte (VM isolée)
- VM Whonix (Gateway + Workstation) : UNIQUE point d'accès au réseau Tor ; aucune collecte avant validation de l'encadrant.
- Aucun compte personnel, aucun identifiant réel, aucune interaction avec des acteurs, aucun téléchargement de fichiers.
- Chaque session = une ligne dans `journals/journal_collecte_darkweb.csv` (outil : `thab.journal.log_collect_session`).
- Contenu illicite rencontré (CSAM, etc.) : arrêt immédiat, aucune capture, signalement à l'encadrant.
