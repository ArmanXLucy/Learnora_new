"""
Cold-Start Assessment Engine.
Turns a learner's quiz answers into an initial skill/knowledge profile
(the "mastered topics" set) without needing any prior interaction history.
"""
from .skill_graph import COLD_START_QUESTIONS, topic_order, SKILLS

MASTERY_THRESHOLD = 0.6  # fraction correct needed to call a topic "mastered"


def score_quiz(skill_id, answers, question_bank=None):
    """
    answers: dict of { topic_id: [selected_option_index, ...] } in the same
             order as the question bank for that topic.
    question_bank: optional {topic_id: [questions]} — pass the SAME trimmed
             bank that was shown to the learner (see get_quiz_questions), so
             scoring lines up with what they actually answered. Defaults to
             the full COLD_START_QUESTIONS bank.
    Returns: {
        "topic_scores": {topic_id: fraction_correct},
        "mastered": set(topic_id, ...),
    }
    """
    bank = question_bank if question_bank is not None else COLD_START_QUESTIONS
    topics = SKILLS[skill_id]["topics"]
    topic_scores = {}
    mastered = set()

    for topic in topics:
        questions = bank.get(topic, [])
        given = answers.get(topic, [])
        if not questions:
            continue
        correct = 0
        for i, q in enumerate(questions):
            if i < len(given) and given[i] == q["answer"]:
                correct += 1
        frac = correct / len(questions)
        topic_scores[topic] = round(frac, 2)
        if frac >= MASTERY_THRESHOLD:
            mastered.add(topic)

    # Enforce prerequisite consistency: a topic can only truly count as
    # "mastered" for roadmap purposes if the learner also mastered (or the
    # quiz didn't test) everything before it in topological order. This
    # avoids a lucky guess on an advanced topic skipping real gaps.
    ordered = topic_order(skill_id)
    consistent_mastered = set()
    broken = False
    for t in ordered:
        if t in mastered and not broken:
            consistent_mastered.add(t)
        else:
            broken = True if t not in mastered else broken

    return {
        "topic_scores": topic_scores,
        "mastered": consistent_mastered,
        "raw_mastered": mastered,
    }


def get_effective_question_count(hours_per_week):
    """Scales assessment depth to the learner's stated weekly commitment:
    a very time-constrained learner gets a quicker assessment, a highly
    available learner gets the full one. This addresses the earlier gap
    where every learner got an identical-length assessment regardless of
    how much time they said they could realistically commit."""
    if hours_per_week is None:
        return None  # no trimming — use full bank
    if hours_per_week <= 2:
        return 1
    if hours_per_week <= 6:
        return 2
    return None  # full bank (up to 3 questions per topic)


def get_quiz_questions(skill_id, hours_per_week=None):
    """Return the quiz question bank for a skill, without revealing answers to the client-render step (answers stripped client-side in template)."""
    topics = SKILLS[skill_id]["topics"]
    n = get_effective_question_count(hours_per_week)
    result = {}
    for t in topics:
        qs = COLD_START_QUESTIONS.get(t, [])
        result[t] = qs[:n] if n else qs
    return result
