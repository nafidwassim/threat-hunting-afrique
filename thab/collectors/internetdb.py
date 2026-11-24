"""Surface d'attaque : Shodan InternetDB (API gratuite, sans clé) - source SRC-002.
Utilisé uniquement sur des IP du laboratoire / des profils fictifs."""
from __future__ import annotations
from .. import sources

RISKY_PORTS = {23: "telnet", 445: "smb", 3389: "rdp", 5900: "vnc", 1433: "mssql", 3306: "mysql", 9200: "elasticsearch"}


def summarize(record: dict) -> dict:
    ports = sorted(record.get("ports", []))
    vulns = sorted(record.get("vulns", []))
    risky = {p: RISKY_PORTS[p] for p in ports if p in RISKY_PORTS}
    return {"ip": record.get("ip"), "ports": ports, "risky_ports": risky, "cves": vulns,
            "hostnames": record.get("hostnames", []), "tags": record.get("tags", []),
            "priority": "haute" if vulns or risky else "normale"}


def fetch(ip: str, timeout: int = 20) -> dict:
    sources.require_validated("SRC-002")
    import requests
    r = requests.get(f"https://internetdb.shodan.io/{ip}", timeout=timeout)
    if r.status_code == 404:
        return {"ip": ip, "ports": [], "vulns": []}
    r.raise_for_status()
    return r.json()
