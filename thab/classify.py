"""Classification des publications collectées en catégories de menace (TF-IDF + régression logistique).
Évaluation : validation croisée stratifiée, précision / rappel par classe."""
from __future__ import annotations
from pathlib import Path
import csv

DATA = Path(__file__).resolve().parent.parent / "data" / "annotated" / "publications_annotated.csv"


def load_dataset(path: Path | None = None) -> list[dict]:
    with open(path or DATA, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def build_model():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    return make_pipeline(TfidfVectorizer(strip_accents="unicode", lowercase=True, ngram_range=(1, 2), sublinear_tf=True),
                         LogisticRegression(max_iter=2000, C=10.0, class_weight="balanced"))


def evaluate(rows: list[dict] | None = None, folds: int = 5, seed: int = 42) -> dict:
    from sklearn.metrics import classification_report
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    rows = rows or load_dataset()
    X = [r["title"] + ". " + r["text"] for r in rows]
    y = [r["category"] for r in rows]
    pred = cross_val_predict(build_model(), X, y, cv=StratifiedKFold(folds, shuffle=True, random_state=seed))
    return classification_report(y, pred, output_dict=True, zero_division=0)


def train(rows: list[dict] | None = None):
    rows = rows or load_dataset()
    model = build_model()
    model.fit([r["title"] + ". " + r["text"] for r in rows], [r["category"] for r in rows])
    return model


# --- Lexique bilingue FR/EN (règles) : première ligne de classification, repli sur le modèle ML --------------------
# ATTENTION : ce lexique a été rédigé en connaissant le jeu annoté ; son évaluation sur ce jeu est donc optimiste.
# La vraie mesure se fera sur les items réels collectés avant le mi-parcours.
LEXICON = {
    "ransomware": ["ransomware", "rancongiciel", "chiffrement", "chiffre", "encrypt", "leak site", "ransom"],
    "data_leak_sale": ["leak", "fuite", "credential", "identifiants", "stealer", "dump", "database", "base d",
                       "access broker", "initial access", "vente", "on sale", "breach", "publi"],
    "hacktivism_ddos": ["ddos", "hacktiv", "defigur", "deface", "revendication", "revendique", "boycott", "attaques coordonn"],
    "mobile_money_fraud": ["sim swap", "mobile money", "ussd", "kyc", "wallet", "portefeuille", "clonage", "3d secure",
                           "synthetic identit", "echange de sim", "sim card", "mobile wallet"],
    "phishing_bec": ["phishing", "business email", "bec", "vishing", "faux conseiller", "sms imitant", "fake invoice",
                     "fake supplier", "faux courriel", "faux sms", "impersonat", "detournement de paiement"],
    "vuln_exploit": ["vulnerab", "cve", "exploit", "flaw", "zero-day", "remote code execution", "authentication bypass",
                     "trojanized", "known exploited", "under attack"],
}
PRIORITY = ["vuln_exploit", "ransomware", "mobile_money_fraud", "phishing_bec", "hacktivism_ddos", "data_leak_sale"]


def _plain(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def lexicon_scores(text: str) -> dict[str, int]:
    t = _plain(text)
    return {cat: sum(1 for w in words if w in t) for cat, words in LEXICON.items()}


def predict_hybrid(text: str, model=None) -> str:
    """Lexique si un gagnant net existe, sinon modèle ML ; 'hors_sujet' si ni l'un ni l'autre ne trouve d'indice."""
    sc = lexicon_scores(text)
    best = max(sc.values())
    if best == 0:
        return "hors_sujet"
    winners = [c for c in PRIORITY if sc[c] == best]
    if len(winners) == 1:
        return winners[0]
    if model is not None:
        ml = model.predict([text])[0]
        if ml in winners:
            return ml
    return winners[0]


def evaluate_hybrid(rows: list[dict] | None = None, folds: int = 5, seed: int = 42) -> dict:
    from sklearn.metrics import classification_report
    from sklearn.model_selection import StratifiedKFold
    rows = rows or load_dataset()
    X = [r["title"] + ". " + r["text"] for r in rows]
    y = [r["category"] for r in rows]
    pred = [None] * len(rows)
    for tr, te in StratifiedKFold(folds, shuffle=True, random_state=seed).split(X, y):
        m = build_model().fit([X[i] for i in tr], [y[i] for i in tr])
        for i in te:
            pred[i] = predict_hybrid(X[i], m)
    return classification_report(y, pred, output_dict=True, zero_division=0), pred
