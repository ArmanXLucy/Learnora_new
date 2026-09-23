"""
Recommendation Engine.

Content-based component: TF-IDF vectorization of each course's (topic's)
skill-tag keywords, compared against the learner's skill-gap vector via
cosine similarity.

Context-based component: available-hours-per-week fit, prerequisite
readiness, and current-level difficulty match.

Every scoring component can be toggled off, which is what powers the
ablation study in ml/evaluate.py (full model vs each component removed
vs a plain-cosine-similarity baseline).
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from .skill_graph import TOPIC_META, build_roadmap, is_ready


def _learner_gap_text(gap_topics):
    """Concatenate keywords of every gap topic into one 'learner need' document."""
    return " ".join(TOPIC_META[t["topic_id"]]["keywords"] for t in gap_topics)


def _difficulty_fit(topic_difficulty, learner_level):
    """1.0 = perfect difficulty match to learner's current level, decays with distance."""
    dist = abs(topic_difficulty - learner_level)
    return max(0.0, 1.0 - dist / 4.0)


def recommend(skill_id, mastered_set, hours_per_week=5, top_k=5,
              use_similarity=True, use_gap_weight=True,
              use_prereq_weight=True, use_context_filter=True):
    """
    Returns a ranked list of recommendation dicts for the learner's current
    skill gap. Toggling the use_* flags produces ablation variants.
    """
    roadmap = build_roadmap(skill_id, mastered_set)
    gap_topics = [t for t in roadmap if t["status"] != "mastered"]
    if not gap_topics:
        return []

    mastered_set = set(mastered_set)
    learner_level = 1
    if mastered_set:
        learner_level = max(TOPIC_META[t]["difficulty"] for t in mastered_set)

    # ---- TF-IDF cosine similarity: gap-need text vs each topic's keywords ----
    gap_text = _learner_gap_text(gap_topics)
    corpus = [gap_text] + [TOPIC_META[t["topic_id"]]["keywords"] for t in gap_topics]
    vectorizer = TfidfVectorizer()
    tfidf = vectorizer.fit_transform(corpus)
    sims = cosine_similarity(tfidf[0:1], tfidf[1:]).flatten()

    results = []
    for i, topic in enumerate(gap_topics):
        sim_score = float(sims[i]) if use_similarity else 0.5  # neutral baseline value

        ready = is_ready(topic["topic_id"], mastered_set)
        prereq_score = 1.0 if ready else 0.2
        if not use_prereq_weight:
            prereq_score = 1.0  # ignore readiness entirely

        # gap-coverage weighting: topics earlier in the unmet chain matter more
        position_weight = 1.0 - (i / max(1, len(gap_topics)))
        gap_weight = position_weight if use_gap_weight else 0.5

        diff_fit = _difficulty_fit(topic["difficulty"], learner_level)

        context_ok = True
        if use_context_filter:
            # a topic "fits" the weekly time budget if it can be finished
            # within ~2 weeks at the learner's stated pace
            context_ok = topic["hours"] <= max(hours_per_week * 2, 1)
        context_score = 1.0 if context_ok else 0.4

        final_score = (
            0.35 * sim_score +
            0.30 * gap_weight +
            0.20 * prereq_score +
            0.15 * (diff_fit * context_score)
        )

        reasons = []
        if ready:
            reasons.append("its prerequisites are already covered")
        else:
            reasons.append("it is the next topic in your roadmap")
        if sim_score > 0.3:
            reasons.append("its content closely matches your current skill gap")
        if context_ok:
            reasons.append(f"it fits your {hours_per_week}-hrs/week availability")
        explanation = f"Recommended because {', and '.join(reasons)}."

        results.append({
            "topic_id": topic["topic_id"],
            "display": topic["display"],
            "difficulty": topic["difficulty"],
            "hours": topic["hours"],
            "status": topic["status"],
            "similarity_score": round(sim_score, 3),
            "gap_weight": round(gap_weight, 3),
            "prereq_score": round(prereq_score, 3),
            "context_ok": context_ok,
            "final_score": round(float(final_score), 4),
            "explanation": explanation,
        })

    results.sort(key=lambda r: r["final_score"], reverse=True)
    return results[:top_k]


def plain_cosine_baseline(skill_id, mastered_set, top_k=5):
    """The 'plain cosine similarity baseline' referenced in the ablation study:
    ranks purely by TF-IDF similarity, ignoring gap position, prerequisites and context."""
    return recommend(skill_id, mastered_set, top_k=top_k,
                      use_similarity=True, use_gap_weight=False,
                      use_prereq_weight=False, use_context_filter=False)
