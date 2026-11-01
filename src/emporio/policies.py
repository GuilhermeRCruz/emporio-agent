"""Interchangeable ways for the agent to read the store policy manual.

sections    The model picks a section key from a closed list; Python returns that section.
            No retrieval step that can miss, no extra network call.
rag_parent  The question is embedded (Gemini embeddings) and matched against subsection chunks;
            the whole sections those chunks belong to are returned (parent document retrieval).
            A plain chunk RAG was measured too and removed: same accuracy and latency, but it
            could cut the context a follow-up needed (evals/history/three_modes).

POLICY_MODE selects which one the agent gets. The evals run all of them.
"""

import json
from functools import lru_cache

import numpy as np
from google.genai import types

from emporio import llm
from emporio.config import EMBEDDINGS_PATH, GEMINI_EMBEDDING_MODEL, POLICIES_PATH

RAG_TOP_K = 3
PARENT_MAX_SECTIONS = 2  # top chunks often span two sections (garantia + trocas)
EMBEDDING_DIMENSIONS = 768


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


def _embed(texts: list[str], task_type: str) -> np.ndarray:
    response = llm.client().models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBEDDING_DIMENSIONS),
    )
    vectors = np.array([e.values for e in response.embeddings], dtype=np.float32)
    # truncated Gemini embeddings are not unit length; normalise so dot product = cosine
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


@lru_cache(maxsize=1)
def _chunk_index() -> np.ndarray:
    """Chunk embeddings, cached on disk and rebuilt if the chunks or the model change."""
    chunks = load()["chunks"]
    signature = f"{GEMINI_EMBEDDING_MODEL}|{EMBEDDING_DIMENSIONS}|" + "|".join(_chunk_text(c) for c in chunks)
    if EMBEDDINGS_PATH.exists():
        cached = np.load(EMBEDDINGS_PATH)
        if str(cached["signature"]) == signature:
            return cached["vectors"]
    vectors = _embed([_chunk_text(c) for c in chunks], "RETRIEVAL_DOCUMENT")
    np.savez(EMBEDDINGS_PATH, vectors=vectors, signature=np.array(signature))
    return vectors


def _rank(question: str) -> tuple[list[dict], np.ndarray, np.ndarray]:
    chunks = load()["chunks"]
    scores = _chunk_index() @ _embed([question], "RETRIEVAL_QUERY")[0]
    return chunks, scores, np.argsort(-scores)


def search_parent(question: str, top_k: int = RAG_TOP_K, max_sections: int = PARENT_MAX_SECTIONS) -> dict:
    """Parent document retrieval: match on the small chunks, return their whole sections.

    Small chunks keep the match precise; the parent section gives the model the rest of the
    context (asking about strings returns 8.3, but the answer to the follow-up lives in 8.2).
    """
    chunks, scores, order = _rank(question)
    sections, seen = [], set()
    for i in order[:top_k]:
        key = chunks[i]["section"]
        if key not in seen:
            seen.add(key)
            sections.append(get_section(key) | {"similaridade": round(float(scores[i]), 3)})
        if len(sections) == max_sections:
            break
    return {"secoes": sections}
