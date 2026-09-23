# Learnora — OpenRouter setup

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

## 2. Configure `.env`

```env
OPENROUTER_API_KEY=YOUR_OPENROUTER_API_KEY
OPENROUTER_MODEL=openrouter/free
```

Do not commit or share `.env`.

## 3. Start Learnora

Restart Flask after changing `.env`.

The application now imports `ml.openrouter_learning` for:
- syllabus analysis
- 3-set (21-question) diagnostic generation
- diagnostic level classification

Temporary provider/rate-limit failures are retried. A failed AI request is
not converted into a fake 0% diagnostic.

Text, PDF and DOCX syllabi are extracted locally. JPG/PNG syllabi are sent as
vision input; `openrouter/free` must select a vision-capable provider for those
requests. If image parsing fails, paste the syllabus text instead.

## Diagnostic structure

- Set 1: 7 Foundation questions
- Set 2: 7 Intermediate questions
- Set 3: 7 Advanced questions
- Total: 21 questions
