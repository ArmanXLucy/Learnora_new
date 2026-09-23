"""
Course-Knowledge-Skill Graph.
Builds a prerequisite DAG per skill using networkx and provides
roadmap ordering + readiness checks.
"""
import json
import os
import networkx as nx

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "curriculum.json")

with open(DATA_PATH, "r", encoding="utf-8") as f:
    CURRICULUM = json.load(f)

SKILLS = CURRICULUM["skills"]
PREREQS = CURRICULUM["prerequisites"]
TOPIC_META = CURRICULUM["topic_meta"]
COLD_START_QUESTIONS = CURRICULUM["cold_start_questions"]
CREATORS = CURRICULUM["creators"]
FLAGSHIP_VIDEOS = CURRICULUM.get("flagship_videos", {})
PLAYLISTS = CURRICULUM.get("playlists", {})


def build_graph(skill_id):
    """Build a directed graph for a skill: edge prereq -> topic."""
    topics = SKILLS[skill_id]["topics"]
    g = nx.DiGraph()
    g.add_nodes_from(topics)
    for topic in topics:
        for prereq in PREREQS.get(topic, []):
            if prereq in topics:
                g.add_edge(prereq, topic)
    return g


def topic_order(skill_id):
    """Topologically sorted topic list respecting prerequisites."""
    g = build_graph(skill_id)
    return list(nx.topological_sort(g))


def get_prereqs(topic_id):
    return PREREQS.get(topic_id, [])


def is_ready(topic_id, mastered_set):
    """A topic is ready to learn if all its prerequisites are mastered."""
    return all(p in mastered_set for p in get_prereqs(topic_id))


def build_roadmap(skill_id, mastered_set):
    """
    Returns an ordered list of dicts describing every topic in the skill,
    in learn-order, with a status: 'mastered' | 'ready' | 'locked'.
    """
    order = topic_order(skill_id)
    roadmap = []
    mastered_set = set(mastered_set)
    for topic in order:
        if topic in mastered_set:
            status = "mastered"
        elif is_ready(topic, mastered_set):
            status = "ready"
        else:
            status = "locked"
        meta = TOPIC_META[topic]
        roadmap.append({
            "topic_id": topic,
            "display": meta["display"],
            "difficulty": meta["difficulty"],
            "hours": meta["hours"],
            "keywords": meta["keywords"],
            "status": status,
        })
    return roadmap


def next_recommended_topics(skill_id, mastered_set, limit=5):
    """The gap topics that are currently 'ready' (prereqs satisfied), in order."""
    roadmap = build_roadmap(skill_id, mastered_set)
    ready = [t for t in roadmap if t["status"] == "ready"]
    return ready[:limit]


def estimate_topic_start_seconds(skill_id, topic_id):
    """
    Best-effort ESTIMATE of where a topic likely starts within a flagship
    full-course video, based on the topic's position in the skill's topic
    order and the video's total duration. This is NOT a verified chapter
    timestamp (we don't have per-video chapter data for these) — it's a
    proportional estimate, clearly labeled as such in the UI, which is still
    far better than always starting at 0:00 for a multi-hour course.
    """
    flagship = FLAGSHIP_VIDEOS.get(skill_id)
    if not flagship or "duration_seconds" not in flagship:
        return 0
    order = SKILLS[skill_id]["topics"]
    if topic_id not in order:
        return 0
    position = order.index(topic_id)
    # small head start so we don't land mid-sentence; also skip most of the
    # video's setup/intro time proportionally
    fraction = position / max(1, len(order))
    return int(fraction * flagship["duration_seconds"])


def full_gap(skill_id, mastered_set):
    """All topics not yet mastered (the full skill gap, ordered)."""
    roadmap = build_roadmap(skill_id, mastered_set)
    return [t for t in roadmap if t["status"] != "mastered"]
