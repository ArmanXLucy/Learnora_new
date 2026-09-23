"""
Open-source, offline AI chatbot.
Retrieval-based: matches the learner's message against a small knowledge
base of topic explanations + platform FAQ using TF-IDF + cosine similarity.
No paid API required.
"""
import json
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge_base.json")

with open(KB_PATH, "r", encoding="utf-8") as f:
    KB = json.load(f)

_docs = []
_entries = []
for entry in KB:
    if entry["tag"] == "fallback":
        continue
    text = " ".join(entry["patterns"])
    _docs.append(text)
    _entries.append(entry)

_vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
_matrix = _vectorizer.fit_transform(_docs) if _docs else None

_FALLBACK = next((e["response"] for e in KB if e["tag"] == "fallback"), "I'm not sure about that yet.")

SIM_THRESHOLD = 0.10

# Build a second index over every topic in the curriculum (not just the
# curated knowledge-base entries) so the bot can give a grounded answer
# about ANY topic in the roadmap, even ones without a hand-written entry.
from .skill_graph import TOPIC_META  # noqa: E402

_topic_ids = list(TOPIC_META.keys())
_topic_docs = [f"{TOPIC_META[t]['display']} {TOPIC_META[t]['keywords']}" for t in _topic_ids]
_topic_vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
_topic_matrix = _topic_vectorizer.fit_transform(_topic_docs) if _topic_docs else None
TOPIC_SIM_THRESHOLD = 0.12


def _dynamic_topic_answer(message):
    """Match the message against every known topic's keywords as a fallback,
    so questions about topics without a curated knowledge-base entry still
    get a real, grounded answer instead of a generic 'I don't know'."""
    if _topic_matrix is None:
        return None
    q_vec = _topic_vectorizer.transform([message])
    sims = cosine_similarity(q_vec, _topic_matrix).flatten()
    best_idx = sims.argmax()
    if sims[best_idx] >= TOPIC_SIM_THRESHOLD:
        topic_id = _topic_ids[best_idx]
        meta = TOPIC_META[topic_id]
        return (f"On {meta['display']}: this topic covers {meta['keywords']}. "
                f"Ask me something more specific about it, or open it from your roadmap for videos and a quick test.")
    return None


def get_response(message, current_topic=None):
    if not message:
        return _FALLBACK

    q_vec = _vectorizer.transform([message]) if _matrix is not None else None
    best_score = 0.0
    best_idx = None
    if q_vec is not None:
        sims = cosine_similarity(q_vec, _matrix).flatten()
        best_idx = sims.argmax()
        best_score = sims[best_idx]

    if best_idx is not None and best_score >= SIM_THRESHOLD:
        return _entries[best_idx]["response"]

    # Try a grounded answer from ANY curriculum topic before giving up
    dynamic = _dynamic_topic_answer(message)
    if dynamic:
        return dynamic

    # fall back to explaining the current topic if we have context
    if current_topic:
        meta = TOPIC_META.get(current_topic)
        if meta:
            return (f"I don't have a specific answer for that, but here's a quick pointer on "
                    f"{meta['display']}: it covers {meta['keywords']}. Try asking something more specific!")
    return _FALLBACK
