import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .text import slugify, words

STOPWORDS = set(
    "a al algo como con cual cuales cuando cuanto cuanta cuantos de del donde e el ella en es esta este hay "
    "la las le les lo los me mi mis mucho muy no o os para pero por puedo puede que se si sin sobre su sus "
    "te tengo ti tu tus un una uno unos y ya yo vosotros vuestra vuestro abris teneis hola buenas gracias".split()
)


@dataclass(frozen=True)
class Chunk:
    id: str
    source: str
    title: str
    text: str


def load_chunks(directory: str | Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(Path(directory).glob("*.md")):
        title, lines = None, []

        def flush():
            body = " ".join(line.strip() for line in lines if line.strip())
            if title and body:
                chunks.append(Chunk(f"{path.stem}#{slugify(title)}", path.stem, title, body))

        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                flush()
                title, lines = line[3:].strip(), []
            elif line.startswith("#") or line.startswith(">"):
                continue
            else:
                lines.append(line)
        flush()
    return chunks


def _terms(text: str) -> list[str]:
    return [w[:5] for w in words(text) if w not in STOPWORDS and len(w) > 1]


class Retriever:
    """Small BM25 over section chunks: enough for a one-business FAQ, no embeddings service needed."""

    def __init__(self, chunks: list[Chunk], k1: float = 1.4, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.docs = [Counter(_terms(f"{c.title} {c.title} {c.text}")) for c in chunks]
        self.avg_len = sum(sum(d.values()) for d in self.docs) / max(len(self.docs), 1)
        df = Counter(term for d in self.docs for term in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 4) -> list[Chunk]:
        q = set(_terms(query))
        scored = []
        for chunk, doc in zip(self.chunks, self.docs):
            length = sum(doc.values())
            score = 0.0
            for term in q & doc.keys():
                tf = doc[term]
                score += self.idf[term] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * length / self.avg_len))
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda s: -s[0])
        return [c for _, c in scored[:k]]
