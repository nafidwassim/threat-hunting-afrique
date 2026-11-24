"""Traffic Light Protocol 2.0 (FIRST) : niveaux et règles de partage minimales."""
from __future__ import annotations

LEVELS = ["TLP:RED", "TLP:AMBER+STRICT", "TLP:AMBER", "TLP:GREEN", "TLP:CLEAR"]  # du plus restrictif au plus ouvert

DEFINITIONS = {
    "TLP:RED": "Réservé aux destinataires nommément désignés ; aucun partage ultérieur.",
    "TLP:AMBER+STRICT": "Diffusion limitée à l'organisation du destinataire, sur la base du besoin d'en connaître.",
    "TLP:AMBER": "Diffusion limitée à l'organisation et à ses clients, selon le besoin d'en connaître.",
    "TLP:GREEN": "Diffusion limitée à la communauté (pairs, partenaires) ; pas de canal public.",
    "TLP:CLEAR": "Aucune limite de divulgation (remplace TLP:WHITE).",
}

# Marquage par défaut selon le type de source : tout ce qui est public est TLP:CLEAR ;
# ce qui provient d'une observation directe restreinte (journal de collecte dark web) démarre plus restrictif.
DEFAULT_BY_SOURCE_TYPE = {
    "cti_institutional": "TLP:CLEAR",
    "cti_vendor": "TLP:CLEAR",
    "cti_open": "TLP:CLEAR",
    "osint_surface": "TLP:CLEAR",
    "telegram_public": "TLP:GREEN",
    "darkweb_index": "TLP:AMBER",
    "darkweb_observation": "TLP:AMBER+STRICT",
}


def normalize(level: str) -> str:
    lv = level.strip().upper().replace("TLP:WHITE", "TLP:CLEAR")
    if not lv.startswith("TLP:"):
        lv = "TLP:" + lv
    if lv not in LEVELS:
        raise ValueError(f"Niveau TLP inconnu : {level!r} ; valeurs admises : {', '.join(LEVELS)}")
    return lv


def default_for(source_type: str) -> str:
    return DEFAULT_BY_SOURCE_TYPE.get(source_type, "TLP:AMBER")


def can_share(level: str, audience: str) -> bool:
    """audience : 'public' | 'community' | 'organisation_and_clients' | 'organisation' | 'named'."""
    order = {"named": 0, "organisation": 1, "organisation_and_clients": 2, "community": 3, "public": 4}
    needed = {"TLP:RED": 0, "TLP:AMBER+STRICT": 1, "TLP:AMBER": 2, "TLP:GREEN": 3, "TLP:CLEAR": 4}
    return order[audience] <= needed[normalize(level)]


def to_misp_tag(level: str) -> str:
    return "tlp:" + normalize(level).split(":", 1)[1].lower()
