"""Extraction d'IOC depuis un texte (y compris les formes "défangées" : hxxp, [.], (dot))."""
from __future__ import annotations
import re

_DEFANG = [
    (re.compile(r"hxxp", re.I), "http"),
    (re.compile(r"\[\.\]|\(\.\)|\[dot\]|\(dot\)", re.I), "."),
    (re.compile(r"\[:\]"), ":"),
    (re.compile(r"\[@\]|\[at\]", re.I), "@"),
]
RE_IPV4 = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
RE_URL = re.compile(r"\bhttps?://[^\s\"'<>)\]]+", re.I)
RE_DOMAIN = re.compile(r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,24})\b", re.I)
RE_SHA256 = re.compile(r"\b[a-f0-9]{64}\b", re.I)
RE_SHA1 = re.compile(r"\b[a-f0-9]{40}\b", re.I)
RE_MD5 = re.compile(r"\b[a-f0-9]{32}\b", re.I)
RE_CVE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.I)
RE_EMAIL = re.compile(r"\b[a-z0-9._%+-]+@(?:[a-z0-9-]+\.)+[a-z]{2,24}\b", re.I)
_FILE_EXT_FP = {"exe", "dll", "pdf", "docx", "xlsx", "zip", "txt", "csv", "png", "jpg", "html", "php", "js", "py", "json"}


def refang(text: str) -> str:
    for pat, rep in _DEFANG:
        text = pat.sub(rep, text)
    return text


def extract(text: str) -> dict[str, list[str]]:
    t = refang(text)
    urls = sorted(set(RE_URL.findall(t)))
    emails = sorted({e.lower() for e in RE_EMAIL.findall(t)})
    ips = sorted(set(RE_IPV4.findall(t)))
    hashes = {
        "sha256": sorted({h.lower() for h in RE_SHA256.findall(t)}),
        "sha1": sorted({h.lower() for h in RE_SHA1.findall(t) if len(h) == 40}),
        "md5": sorted({h.lower() for h in RE_MD5.findall(t) if len(h) == 32}),
    }
    # domaines : on retire ceux déjà couverts par les URL/e-mails et les faux positifs (extensions de fichiers)
    covered = {u.split("/")[2].split(":")[0].lower() for u in urls if u.count("/") >= 2}
    covered |= {e.split("@")[1] for e in emails}
    domains = set()
    for d in RE_DOMAIN.findall(t):
        d = d.lower()
        tld = d.rsplit(".", 1)[-1]
        if tld in _FILE_EXT_FP or d in covered or RE_IPV4.fullmatch(d):
            continue
        domains.add(d)
    domains |= covered
    return {
        "ipv4": ips, "domains": sorted(domains), "urls": urls, "emails": emails,
        "cves": sorted({c.upper() for c in RE_CVE.findall(t)}), **hashes,
    }


def flatten(iocs: dict[str, list[str]]) -> list[tuple[str, str]]:
    return [(k, v) for k, vals in iocs.items() for v in vals]
