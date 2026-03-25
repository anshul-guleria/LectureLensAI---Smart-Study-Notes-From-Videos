"""
app/services/chatbot.py
LectureLensAI — Chatbot Service

Uses LectureLensAI's own Whisper segments (NOT YouTube Transcript API) to
build a per-job FAISS vector store and answer user questions with timestamps.

Features:
- Per-job vector store cached in memory
- Query rewriting using rolling compressed chat history
- Returns { answer, timestamp, standalone_query }
"""

import re
import json
import os
from typing import List, Dict, Any

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableParallel, RunnablePassthrough, RunnableLambda
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv

load_dotenv()

# ── Shared embedding model (loaded once) ──
_embeddings = None

def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return _embeddings


# ── Per-job stores: { job_id: { "retriever":..., "history":[] } } ──
_stores: Dict[str, Dict] = {}


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_timestamp_prompt = PromptTemplate(
    template="""You are a helpful AI tutor that answers questions about a lecture video.

Use ONLY the context below (which includes timestamps) to answer.

Rules:
- Always reference timestamps naturally in your answer.
- If multiple relevant timestamps exist, pick the MOST relevant one.
- If the answer is not in the context, say "Not covered in this lecture" and set timestamp to -1.
- Return ONLY valid JSON.

Context:
{context}

Question:
{query}

Return JSON exactly like this:
{{
    "timestamp": <integer seconds, or -1 if not found>,
    "answer": "<1-3 sentence answer mentioning the timestamp naturally>"
}}""",
    input_variables=["context", "query"],
)

_rewrite_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a query rewriting assistant for a lecture Q&A chatbot.
Return ONLY one standalone question. No explanation.
Use conversation history to resolve references like "it", "that", "this concept", etc.
If history is empty, return the question as-is."""),
    MessagesPlaceholder(variable_name="conversation"),
    ("human", "{query}"),
])

_summarize_history_prompt = PromptTemplate(
    template="""Summarize these Q&A exchanges from a lecture chatbot into 2-3 bullet points.
Keep it factual and concise — this will be used as compressed context for future questions.

Exchanges:
{exchanges}

Summary (bullet points):""",
    input_variables=["exchanges"],
)


# ---------------------------------------------------------------------------
# Vector Store helpers
# ---------------------------------------------------------------------------

def _build_chunks(segments: List[Dict], chunk_size: int = 400) -> List[Document]:
    """Group Whisper segments into chunked Documents with start/end metadata."""
    docs = []
    current_text = ""
    start_time = None

    for seg in segments:
        text = seg.get("text", "").strip()
        seg_start = float(seg.get("start", 0))
        seg_end = float(seg.get("end", seg_start + float(seg.get("duration", 5))))

        if start_time is None:
            start_time = seg_start

        current_text += " " + text

        if len(current_text.split()) >= chunk_size:
            docs.append(Document(
                page_content=current_text.strip(),
                metadata={"start": start_time, "end": seg_end}
            ))
            current_text = ""
            start_time = None

    # Flush remaining
    if current_text.strip() and start_time is not None:
        docs.append(Document(
            page_content=current_text.strip(),
            metadata={"start": start_time, "end": seg_end if segments else 0}
        ))

    return docs


def _init_store(job_id: str, segments: List[Dict]):
    """Build and cache a FAISS vector store from segments for this job."""
    docs = _build_chunks(segments)
    if not docs:
        raise ValueError("No transcript segments provided to build the chatbot.")

    vs = FAISS.from_documents(docs, _get_embeddings())
    _stores[job_id] = {
        "retriever": vs.as_retriever(search_type="similarity", search_kwargs={"k": 4}),
        "history": [],   # List of HumanMessage / AIMessage
        "raw_turns": [], # List of { "q":..., "a":... } for summarization
    }


def get_or_create_store(job_id: str, segments: List[Dict]):
    """Return existing store or create a new one."""
    if job_id not in _stores:
        _init_store(job_id, segments)
    return _stores[job_id]


# ---------------------------------------------------------------------------
# Chat History Compression
# ---------------------------------------------------------------------------

def _maybe_compress_history(store: Dict):
    """
    After every 6 turns, summarise the oldest 4 into a single AIMessage summary
    and replace them in the history list — keeps context window small.
    """
    raw = store["raw_turns"]
    if len(raw) < 6:
        return

    to_summarize = raw[:4]
    exchanges_text = "\n".join(
        f"Q: {t['q']}\nA: {t['a']}" for t in to_summarize
    )

    llm = ChatGroq(model="meta-llama/llama-4-scout-17b-16e-instruct", temperature=0)
    parser = StrOutputParser()
    summary = (llm | parser).invoke(
        _summarize_history_prompt.format(exchanges=exchanges_text)
    )

    # Replace first 4 raw turns with summary, rebuild history
    store["raw_turns"] = raw[4:]
    new_history = [
        HumanMessage(content="[Previous conversation summary]"),
        AIMessage(content=summary),
    ] + [
        msg for turn in store["raw_turns"]
        for msg in [HumanMessage(content=turn["q"]), AIMessage(content=turn["a"])]
    ]
    store["history"] = new_history


# ---------------------------------------------------------------------------
# Query Processing
# ---------------------------------------------------------------------------

def _format_context(docs: List[Document]) -> str:
    parts = []
    for d in docs:
        s = int(d.metadata.get("start", 0))
        e = int(d.metadata.get("end", 0))
        parts.append(f"[{s}s – {e}s]\n{d.page_content}")
    return "\n\n".join(parts)


def _clean_json(text: str) -> str:
    text = re.sub(r"```json|```", "", text)
    text = re.sub(r"(\d+)s\b", r"\1", text)  # remove trailing 's' from timestamps
    return text.strip()


def _parse_response(text: str) -> Dict:
    cleaned = _clean_json(text)
    try:
        data = json.loads(cleaned)
        ts = int(data.get("timestamp", -1))
        answer = str(data.get("answer", "")).strip()
        return {"timestamp": ts, "answer": answer}
    except Exception:
        return {"timestamp": -1, "answer": text.strip()}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def answer_question(job_id: str, segments: List[Dict], query: str) -> Dict[str, Any]:
    """
    Main entry point.
    Returns { "answer": str, "timestamp": int, "standalone": str }
    """
    store = get_or_create_store(job_id, segments)
    retriever = store["retriever"]
    history = store["history"]

    llm = ChatGroq(model="meta-llama/llama-4-scout-17b-16e-instruct", temperature=0.4)
    parser = StrOutputParser()

    # 1. Rewrite query using history
    rewrite_chain = _rewrite_prompt | llm | parser
    standalone = rewrite_chain.invoke({"conversation": history, "query": query})

    # 2. Retrieve + answer with timestamp
    parallel = RunnableParallel({
        "context": retriever | RunnableLambda(_format_context),
        "query": RunnablePassthrough(),
    })
    main_chain = parallel | _timestamp_prompt | llm | parser
    raw_response = main_chain.invoke(standalone)
    parsed = _parse_response(raw_response)

    # 3. Update history
    store["history"].extend([
        HumanMessage(content=standalone),
        AIMessage(content=parsed["answer"]),
    ])
    store["raw_turns"].append({"q": standalone, "a": parsed["answer"]})

    # 4. Maybe compress
    _maybe_compress_history(store)

    return {
        "answer": parsed["answer"],
        "timestamp": parsed["timestamp"],
        "standalone": standalone,
    }
