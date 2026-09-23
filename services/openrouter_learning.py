"""OpenRouter-backed AI service for Learnora.

Environment:
    OPENROUTER_API_KEY=...
    OPENROUTER_MODEL=openrouter/free

The service uses the OpenAI-compatible OpenRouter API.
"""
import json
import os
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
API_KEY = os.getenv("OPENROUTER_API_KEY")

if not API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY is missing from .env")

client = OpenAI(
    api_key=API_KEY,
    base_url="https://openrouter.ai/api/v1",
)


def chat(
    messages: List[Dict[str, str]],
    *,
    model: Optional[str] = None,
    max_retries: int = 3,
) -> str:
    """Call OpenRouter with exponential backoff for temporary failures."""
    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model or MODEL,
                messages=messages,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            last_error = exc
            # Retry temporary/provider errors; don't silently turn failures into a learner score.
            status = getattr(exc, "status_code", None)
            if status not in (408, 429, 500, 502, 503, 504) and attempt == 0:
                raise
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"OpenRouter request failed after retries: {last_error}")


def generate_roadmap(course: str, syllabus: str, study_hours_per_week: float = 5) -> str:
    prompt = f"""
Create a concise adaptive-learning roadmap for a B.Tech student.

Course: {course}
Study time: {study_hours_per_week} hours/week
Syllabus:
{syllabus}

Return ONLY valid JSON with this structure:
{{
  "course": "...",
  "topics": [
    {{
      "title": "...",
      "difficulty": "Basic|Intermediate|Advanced",
      "prerequisites": ["..."],
      "estimated_hours": 1
    }}
  ]
}}

Use 6-12 meaningful topics. Do not create a multi-year career plan.
"""
    return chat([
        {"role": "system", "content": "You are Learnora, an adaptive learning assistant."},
        {"role": "user", "content": prompt},
    ])


def generate_diagnostic(course: str, roadmap: str, count: int = 7) -> str:
    prompt = f"""
Create exactly {count} diagnostic questions for the course "{course}".
Questions must progress from Basic to Intermediate to Advanced and test actual understanding.
Roadmap:
{roadmap}

Return ONLY valid JSON:
{{
  "questions": [
    {{
      "id": 1,
      "difficulty": "Basic|Intermediate|Advanced",
      "question": "...",
      "options": ["...", "...", "...", "..."],
      "answer": "..."
    }}
  ]
}}
"""
    return chat([
        {"role": "system", "content": "You are Learnora's diagnostic assessment engine."},
        {"role": "user", "content": prompt},
    ])


def evaluate_diagnostic(course: str, questions: str, answers: Dict[str, Any]) -> str:
    prompt = f"""
Evaluate this diagnostic for "{course}".

Questions:
{questions}

Student answers:
{json.dumps(answers, ensure_ascii=False)}

Return ONLY valid JSON:
{{
  "score_percent": 0,
  "correct": 0,
  "total": 7,
  "level": "Basic|Intermediate|Advanced",
  "explanation": "...",
  "recommended_topics": ["..."]
}}

Do not assign Basic merely because an AI request failed. Evaluate only the submitted answers.
"""
    return chat([
        {"role": "system", "content": "You are Learnora's fair adaptive assessment evaluator."},
        {"role": "user", "content": prompt},
    ])
