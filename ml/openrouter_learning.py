"""OpenRouter-powered syllabus analysis and adaptive diagnostic assessment.

The browser never receives the OpenRouter API key. Flask calls OpenRouter
server-side and stores only the generated learning plan/assessment metadata.
"""
import base64
import json
import mimetypes
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from .skill_graph import SKILLS, TOPIC_META

load_dotenv()

OPENROUTER_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openrouter/free"


def _key():
    return os.environ.get("OPENROUTER_API_KEY", "").strip()


def _model():
    return os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def configured():
    return bool(_key())


def _client():
    key = _key()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured. Add it to .env.")
    return OpenAI(api_key=key, base_url=OPENROUTER_URL)


def _extract_json(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
        if not starts:
            raise
        start = min(starts)
        end = max(text.rfind("}"), text.rfind("]"))
        if end > start:
            return json.loads(text[start:end + 1])
        raise


def _chat(messages, *, max_tokens=5000, retries=3):
    client = _client()
    last_error = None
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=_model(),
                messages=messages,
                max_tokens=max_tokens,
            )
            text = response.choices[0].message.content or ""
            if not text.strip():
                raise RuntimeError("OpenRouter returned an empty response.")
            return text
        except Exception as exc:
            last_error = exc
            status = getattr(exc, "status_code", None)
            # Retry common temporary provider/rate-limit errors.
            if attempt < retries - 1 and (status is None or status in {408, 429, 500, 502, 503, 504}):
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"OpenRouter request failed: {exc}") from exc
    raise RuntimeError(f"OpenRouter request failed after retries: {last_error}")


def _generate(messages, *, max_tokens=5000):
    return _extract_json(_chat(messages, max_tokens=max_tokens))


def _curriculum_catalog(skill_id):
    rows = []
    for topic_id in SKILLS[skill_id]["topics"]:
        meta = TOPIC_META[topic_id]
        rows.append({
            "id": topic_id,
            "title": meta["display"],
            "difficulty": meta["difficulty"],
            "keywords": meta["keywords"],
        })
    return rows


def general_plan(skill_id):
    """Return the curated Learnora curriculum for the general-syllabus option."""
    meta = SKILLS[skill_id]
    topics = _curriculum_catalog(skill_id)
    return {
        "title": meta["display_name"],
        "summary": meta["description"],
        "source": "general",
        "selected_topic_ids": [t["id"] for t in topics],
        "topics": topics,
        "roadmap": [
            {"topic_id": t["id"], "reason": "General course sequence", "priority": i + 1}
            for i, t in enumerate(topics)
        ],
    }


def _file_to_content(file_path):
    """Convert syllabus files into OpenRouter-compatible message content.

    Text/PDF/DOCX are extracted locally. Images are sent as base64 image input;
    the selected OpenRouter model must support vision for image syllabi.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext in {".txt", ".md"}:
        return [{"type": "text", "text": path.read_text(encoding="utf-8", errors="replace")[:50000]}]

    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF support requires pypdf. Run: pip install pypdf") from exc
        reader = PdfReader(str(path))
        text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
        if not text.strip():
            raise RuntimeError("No selectable text was found in the PDF. Try a text PDF or paste the syllabus.")
        return [{"type": "text", "text": text[:50000]}]

    if ext == ".docx":
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("DOCX support requires python-docx. Run: pip install python-docx") from exc
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        if not text.strip():
            raise RuntimeError("No readable text was found in the DOCX file.")
        return [{"type": "text", "text": text[:50000]}]

    if ext in {".jpg", ".jpeg", ".png"}:
        mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return [
            {"type": "text", "text": "Read this syllabus image carefully and extract/map its contents."},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
        ]

    raise RuntimeError("Unsupported syllabus format.")


def analyze_syllabus(skill_id, *, text="", file_path=None):
    """Map a learner's syllabus to Learnora's exact curriculum topics."""
    if not configured():
        raise RuntimeError("OpenRouter is not configured. Add OPENROUTER_API_KEY to .env.")

    catalog = json.dumps(_curriculum_catalog(skill_id), ensure_ascii=False)
    prompt = f"""
You are Learnora's curriculum planner.

Course: {SKILLS[skill_id]['display_name']}
Course description: {SKILLS[skill_id]['description']}

Learnora's exact content catalog:
{catalog}

Analyze the learner's syllabus and map it to the closest exact Learnora topics.
You MUST use only topic ids from the catalog.
Preserve syllabus order where possible.

Return ONLY valid JSON:
{{
  "title": "short syllabus title",
  "summary": "2-4 sentence summary",
  "selected_topic_ids": ["topic_id"],
  "roadmap": [
    {{"topic_id":"...", "reason":"why it belongs", "priority":1}}
  ]
}}

If a topic is not present, leave it out. If the syllabus is broad, include
the relevant core catalog topics. Do not invent topic ids.
""".strip()

    if file_path:
        source_parts = _file_to_content(file_path)
        source_parts.append({"type": "text", "text": prompt})
        messages = [
            {"role": "system", "content": "You are Learnora's curriculum planning AI."},
            {"role": "user", "content": source_parts},
        ]
    else:
        messages = [
            {"role": "system", "content": "You are Learnora's curriculum planning AI."},
            {"role": "user", "content": prompt + "\n\nLearner syllabus:\n" + (text or "")[:50000]},
        ]

    result = _generate(messages, max_tokens=5000)
    valid_ids = {x["id"] for x in _curriculum_catalog(skill_id)}
    selected = [x for x in result.get("selected_topic_ids", []) if x in valid_ids]
    if not selected:
        selected = [x["id"] for x in _curriculum_catalog(skill_id)]
    result["selected_topic_ids"] = selected
    result["roadmap"] = [
        r for r in result.get("roadmap", [])
        if isinstance(r, dict) and r.get("topic_id") in valid_ids and r.get("topic_id") in selected
    ]
    return result


def generate_diagnostic(skill_id, topic_ids, syllabus_summary=""):
    """Generate three diagnostic sets of seven MCQs each.

    Set 1 = foundational/basic understanding
    Set 2 = intermediate/application
    Set 3 = advanced/problem-solving
    """
    if not configured():
        raise RuntimeError("OpenRouter is not configured. Add OPENROUTER_API_KEY to .env.")

    catalog = [
        {
            "id": t,
            "title": TOPIC_META[t]["display"],
            "difficulty": TOPIC_META[t]["difficulty"],
            "keywords": TOPIC_META[t]["keywords"],
        }
        for t in topic_ids if t in TOPIC_META
    ]

    prompt = f"""
You are Learnora's diagnostic assessment engine.

Course: {SKILLS[skill_id]['display_name']}
Syllabus summary: {syllabus_summary}

Topics:
{json.dumps(catalog, ensure_ascii=False)}

Create THREE separate diagnostic sets. EACH SET MUST CONTAIN EXACTLY 7
multiple-choice questions.

SET 1 — FOUNDATION:
- 7 questions
- basic/fundamental concepts
- checks whether the learner understands definitions, terminology,
  core concepts and simple examples.

SET 2 — INTERMEDIATE:
- 7 questions
- intermediate concepts
- application, comparison, tracing, calculations or practical situations.
- assume the learner understands the fundamentals.

SET 3 — ADVANCED:
- 7 questions
- advanced concepts
- problem solving, design decisions, deeper reasoning, edge cases,
  trade-offs or code/system analysis.
- questions should distinguish strong understanding from memorization.

Do NOT repeat the same question across sets.
All questions must be relevant to the supplied course topics.
Each question must have exactly 4 options and exactly one correct answer.

Return ONLY valid JSON:
{{
  "sets": [
    {{
      "set_number": 1,
      "title": "Foundation",
      "description": "Basic concepts and fundamentals",
      "questions": [
        {{
          "id": 1,
          "topic_id": "one listed topic id",
          "difficulty": "basic",
          "question": "...",
          "options": ["...","...","...","..."],
          "answer": 0,
          "explanation": "short explanation"
        }}
      ]
    }},
    {{
      "set_number": 2,
      "title": "Intermediate",
      "description": "Application and deeper understanding",
      "questions": [
        {{
          "id": 8,
          "topic_id": "one listed topic id",
          "difficulty": "intermediate",
          "question": "...",
          "options": ["...","...","...","..."],
          "answer": 0,
          "explanation": "short explanation"
        }}
      ]
    }},
    {{
      "set_number": 3,
      "title": "Advanced",
      "description": "Problem solving and advanced reasoning",
      "questions": [
        {{
          "id": 15,
          "topic_id": "one listed topic id",
          "difficulty": "advanced",
          "question": "...",
          "options": ["...","...","...","..."],
          "answer": 0,
          "explanation": "short explanation"
        }}
      ]
    }}
  ]
}}
"""

    result = _generate([
        {"role": "system", "content": "You are Learnora's diagnostic assessment engine."},
        {"role": "user", "content": prompt.strip()},
    ], max_tokens=12000)

    raw_sets = result.get("sets", [])
    if not isinstance(raw_sets, list):
        raise RuntimeError("OpenRouter returned an invalid diagnostic format.")

    clean = []
    allowed = set(topic_ids)
    expected_difficulties = {1: "basic", 2: "intermediate", 3: "advanced"}

    for set_index in range(1, 4):
        source_set = next(
            (x for x in raw_sets if isinstance(x, dict) and int(x.get("set_number", 0) or 0) == set_index),
            None,
        )
        if not source_set:
            continue

        set_questions = source_set.get("questions", [])
        if not isinstance(set_questions, list):
            continue

        valid_set_questions = []
        for q in set_questions:
            if not isinstance(q, dict):
                continue

            opts = q.get("options") or []
            answer = q.get("answer")

            if (
                q.get("topic_id") not in allowed
                or len(opts) != 4
                or not isinstance(answer, int)
                or not 0 <= answer < 4
            ):
                continue

            difficulty = expected_difficulties[set_index]
            valid_set_questions.append({
                "id": len(clean) + len(valid_set_questions) + 1,
                "set_number": set_index,
                "set_title": source_set.get("title") or {
                    1: "Foundation",
                    2: "Intermediate",
                    3: "Advanced",
                }[set_index],
                "difficulty": difficulty,
                "topic_id": q["topic_id"],
                "question": str(q.get("question", "")),
                "options": [str(x) for x in opts],
                "answer": answer,
                "explanation": str(q.get("explanation", "")),
            })

            if len(valid_set_questions) == 7:
                break

        if len(valid_set_questions) != 7:
            raise RuntimeError(
                f"OpenRouter returned only {len(valid_set_questions)} valid questions "
                f"for diagnostic set {set_index}. Please try again."
            )

        clean.extend(valid_set_questions)

    if len(clean) != 21:
        raise RuntimeError(
            f"OpenRouter returned {len(clean)} valid diagnostic questions; Learnora requires 21."
        )

    # Normalize IDs to 1..21 after validation.
    for i, q in enumerate(clean, start=1):
        q["id"] = i

    return clean


def classify_level(questions, answers):
    """Classify the learner without treating an AI outage as a zero score."""
    rows = []
    for q in questions:
        selected = answers.get(str(q["id"]), -1)
        rows.append({
            "id": q["id"],
            "difficulty": q["difficulty"],
            "correct": selected == q["answer"],
            "topic_id": q["topic_id"],
        })

    if configured():
        prompt = f"""
Classify this learner from a 21-question diagnostic consisting of 3 sets:
Set 1 = foundation/basic, Set 2 = intermediate/application, Set 3 = advanced/problem-solving.

{json.dumps(rows, ensure_ascii=False)}

Return ONLY valid JSON:
{{"level":"basic|intermediate|advanced","score":0-100,"reason":"one short sentence"}}

Use the learner's performance across all three sets. A learner who performs
strongly in Set 1 but weakly in Set 2 should not be classified as advanced.


Rules:
- basic: foundational gaps
- intermediate: solid basics plus partial intermediate ability
- advanced: strong intermediate performance and meaningful advanced success
- Never call a learner advanced if they have major basic/intermediate gaps.
"""
        try:
            result = _generate([
                {"role": "system", "content": "You are Learnora's fair adaptive assessment evaluator."},
                {"role": "user", "content": prompt},
            ], max_tokens=500)
            level = str(result.get("level", "")).lower()
            if level in {"basic", "intermediate", "advanced"}:
                return {
                    "level": level,
                    "score": float(result.get("score", 0)),
                    "reason": result.get("reason", ""),
                }
        except Exception:
            # Use the deterministic calculation only when an actual answer set exists.
            pass

    groups = {d: [r for r in rows if r["difficulty"] == d] for d in ("basic", "intermediate", "advanced")}
    rates = {d: (sum(r["correct"] for r in rs) / len(rs) if rs else 0) for d, rs in groups.items()}

    if rates["advanced"] >= 0.5 and rates["intermediate"] >= 0.67 and rates["basic"] >= 0.5:
        level = "advanced"
    elif rates["basic"] >= 0.67 and rates["intermediate"] >= 0.5:
        level = "intermediate"
    else:
        level = "basic"

    score = round(sum(r["correct"] for r in rows) * 100 / max(1, len(rows)), 1)
    return {
        "level": level,
        "score": score,
        "reason": f"Basic {rates['basic']:.0%}, intermediate {rates['intermediate']:.0%}, advanced {rates['advanced']:.0%}.",
    }
