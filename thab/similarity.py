"""Similarité sémantique entre un renseignement et le profil de l'entreprise.

Deux moteurs interchangeables :
- TF-IDF + cosinus (scikit-learn) : léger, déterministe, utilisé par défaut et dans les tests ;
- sentence-transformers (laboratoire, 100 % local) : embeddings multilingues, activé dans scoring.yaml.
"""
from __future__ import annotations
import numpy as np


class TfidfSimilarity:
    name = "tfidf"

    def __init__(self, corpus: list[str]):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vec = TfidfVectorizer(strip_accents="unicode", lowercase=True, ngram_range=(1, 2),
                                   sublinear_tf=True, min_df=1)
        self.vec.fit(corpus)

    def score(self, text_a: str, text_b: str) -> float:
        from sklearn.metrics.pairwise import cosine_similarity
        m = self.vec.transform([text_a, text_b])
        return float(cosine_similarity(m[0], m[1])[0, 0])


class SentenceTransformerSimilarity:
    name = "sentence-transformers"

    def __init__(self, corpus: list[str] | None = None,
                 model: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        from sentence_transformers import SentenceTransformer  # import différé : absent du sandbox
        self.model = SentenceTransformer(model)

    def score(self, text_a: str, text_b: str) -> float:
        a, b = self.model.encode([text_a, text_b], normalize_embeddings=True)
        return float(np.dot(a, b))


def make_backend(kind: str, corpus: list[str]):
    if kind == "sentence-transformers":
        try:
            return SentenceTransformerSimilarity(corpus)
        except ImportError:
            pass  # repli explicite : le journal de validation consigne ce cas
    return TfidfSimilarity(corpus)
