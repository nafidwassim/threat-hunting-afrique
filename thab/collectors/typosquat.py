"""Génération locale de domaines typosquattés (équivalent simplifié de dnstwist) - source SRC-003.
Aucune requête réseau par défaut : la résolution DNS est optionnelle et réservée aux domaines de test."""
from __future__ import annotations

HOMOGLYPHS = {"a": ["4", "à"], "e": ["3"], "i": ["1", "l"], "l": ["1", "i"], "o": ["0"], "s": ["5"], "m": ["rn"], "w": ["vv"]}
TLD_SWAPS = ["com", "net", "org", "co", "info", "online", "ma", "ci"]


def permutations(domain: str) -> set[str]:
    name, _, tld = domain.rpartition(".")
    out: set[str] = set()
    for i in range(len(name)):
        out.add(f"{name[:i]}{name[i+1:]}.{tld}")                      # omission
        out.add(f"{name[:i]}{name[i]}{name[i:]}.{tld}")               # répétition
        if i < len(name) - 1:
            out.add(f"{name[:i]}{name[i+1]}{name[i]}{name[i+2:]}.{tld}")   # transposition
        for g in HOMOGLYPHS.get(name[i], []):
            out.add(f"{name[:i]}{g}{name[i+1:]}.{tld}")               # homoglyphe
    for i in range(1, len(name)):
        out.add(f"{name[:i]}-{name[i:]}.{tld}")                      # tiret
    for t in TLD_SWAPS:
        out.add(f"{name}.{t}")                                       # changement de TLD
    out.add(f"{name}-secure.{tld}")
    out.add(f"login-{name}.{tld}")
    out.discard(domain)
    return {d for d in out if d and not d.startswith(("-", ".")) and "--" not in d and ".." not in d}


def resolve(domains: list[str]) -> dict[str, str | None]:
    """Résolution DNS - à n'utiliser que sur les domaines de test du laboratoire."""
    import socket
    res = {}
    for d in domains:
        try:
            res[d] = socket.gethostbyname(d)
        except OSError:
            res[d] = None
    return res
