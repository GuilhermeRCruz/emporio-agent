"""Two interchangeable ways for the agent to read the store policy manual.

sections  The model picks a section key from a closed list; Python returns that section.
          No retrieval step that can miss, no extra network call.
rag       The question is embedded and the closest subsection chunks are returned.

POLICY_MODE selects which one the agent gets. The evals run both.
"""

import json
from functools import lru_cache

import numpy as np

from emporio.config import EMBEDDINGS_PATH, OPENAI_EMBEDDING_MODEL, POLICIES_PATH

RAG_TOP_K = 3


@lru_cache(maxsize=1)
def load() -> dict:
    return json.loads(POLICIES_PATH.read_text(encoding="utf-8"))


def section_keys() -> list[str]:
    return [s["key"] for s in load()["sections"]]


def get_section(section: str) -> dict:
    for s in load()["sections"]:
        if s["key"] == section:
            return {"secao": s["title"], "texto": s["text"]}
    return {"erro": f"Seção inexistente. Opções: {', '.join(section_keys())}"}


def _chunk_text(chunk: dict) -> str:
    return f"{chunk['title']}\n{chunk['text']}"


def _embed(client, texts: list[str]) -> np.ndarray:
    response = client.embeddings.create(model=OPENAI_EMBEDDING_MODEL, input=texts)
    vectors = np.array([d.embedding for d in response.data], dtype=np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


@lru_cache(maxsize=1)
def _chunk_index(client) -> np.ndarray:
    """Chunk embeddings, cached on disk and rebuilt if the chunks or the model change."""
    chunks = load()["chunks"]
    signature = OPENAI_EMBEDDING_MODEL + "|" + "|".join(_chunk_text(c) for c in chunks)
    if EMBEDDINGS_PATH.exists():
        cached = np.load(EMBEDDINGS_PATH)
        if str(cached["signature"]) == signature:
            return cached["vectors"]
    vectors = _embed(client, [_chunk_text(c) for c in chunks])
    np.savez(EMBEDDINGS_PATH, vectors=vectors, signature=np.array(signature))
    return vectors


def search(client, question: str, top_k: int = RAG_TOP_K) -> dict:
    chunks = load()["chunks"]
    index = _chunk_index(client)
    query = _embed(client, [question])[0]
    scores = index @ query
    best = np.argsort(-scores)[:top_k]
    return {
        "trechos": [
            {"secao": chunks[i]["title"], "texto": chunks[i]["text"], "similaridade": round(float(scores[i]), 3)}
            for i in best
        ]
    }
