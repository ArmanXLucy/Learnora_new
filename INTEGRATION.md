# Learnora — integration notes

This project is the **Learnora landing page** and the **SkillGapPath learning
platform** merged into a single Flask application.

Everything below documents *how the merge was done*. For the deeper explanation
of the recommendation engine, skill graph and evaluation metrics, see
`README.md` (the original SkillGapPath documentation, unchanged).

---

## 1. Run it

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open <http://127.0.0.1:5000>.

You land on the Learnora marketing page. Sign up or log in, and from that point
on the whole SkillGapPath product takes over — dashboard, assessment, roadmap,
topic pages, chatbot, admin — all wearing the Learnora design.

Admin login: `admin` / `admin123` (change via `.env` → `ADMIN_USERNAME` /
`ADMIN_PASSWORD`). Pick "Login as Admin" on the login screen.

---

## 2. Why the two zips were merged this way

The landing page was a **React + Vite** app. The learning platform is a
**Flask + Jinja** app with a SQLite database, an ML recommendation layer and
server-side sessions. Those cannot be nested inside one another without either
rebuilding the backend in JS or running two servers behind a proxy.

So the Flask app became the single application, and the React landing page was
**ported to server-rendered Jinja templates**. Practical consequences:

- One process, one command, no `npm install` and no build step.
- The login flow is real: a session cookie, a real database, real password
  hashing — instead of the landing page's simulated 700 ms login.
- The landing page can read live data (see §4).
- `lucide-react` icons became an inline-SVG Jinja macro, so there is no icon
  dependency at all.

The original React source is preserved untouched in `_react_source/` for
reference. It is not used at runtime and can be deleted.

---

## 3. What changed, file by file

### New files

| File | Purpose |
|---|---|
| `templates/landing.html` | The React landing page as Jinja — hero, ambient motion, product preview, how-it-works, capabilities, courses, paths, pricing, curved gradient footer, scroll reveals, mobile nav |
| `templates/_icons.html` | `icon(name, size)` macro — inline SVG replacements for every lucide-react icon the landing used |
| `templates/auth_base.html` | The landing's split-screen animated auth layout, used by login / register / forgot-password |
| `static/css/learnora.css` | The landing stylesheet verbatim, **plus** an application layer built on the same design tokens |

### Rewritten (presentation only)

`base.html`, `login.html`, `register.html`, `forgot_password.html`,
`dashboard.html`, `start_skill.html`, `quiz.html`, `roadmap.html`,
`topic.html`, `admin_dashboard.html`, `admin_student.html`,
`admin_research.html`.

Every form keeps its original `name` attributes, `pattern` validations and
POST targets. Every piece of page JavaScript (playlist jump, creator tabs,
transcript fetching, the topic self-check answer builder, skill search) was
carried across unchanged.

### Removed

- `templates/intro.html` — the old splash screen that auto-redirected to login
  after 3.2 s. The Learnora landing page is the home page now.
- `static/css/style.css` — the old dark theme, replaced by `learnora.css`.

### Unchanged

`app.py` routes and logic (except §4), `dal.py`, `db.py`, `config.py`,
`youtube.py`, the entire `ml/` package, `data/`, `instance/`,
`static/js/main.js`, `static/js/chatbot.js`.

---

## 4. The three changes to `app.py`

Kept deliberately small, and all additive:

1. **`intro()`** renders `landing.html` instead of `intro.html`, passing
   `SKILLS` so the landing page's course grid is generated from the real skill
   graph. Add a skill to `ml/skill_graph.py` and it appears on the landing page
   automatically — the marketing page and the roadmaps cannot drift apart.

2. **`dashboard()`** additionally computes `week_activity` (a seven-day
   activity strip from the existing activity log), `overall_percent`,
   `total_mastered`, `total_topics` and `next_up`. This is what fills the
   landing design's analytics cards and "Up Next" rail with **real** numbers
   instead of the mock ones the React dashboard displayed. No existing value
   was altered.

3. **`logout()`** redirects to the landing page rather than the login form.

`quiz()` also now passes `TOPIC_META` so the assessment can show proper topic
titles ("Branching & Merging") instead of slugs ("branching_merging").

---

## 5. Two bugs fixed

Both existed in the original learning platform and both silently broke scoring.

**`quiz.html`** — the radio button `name` used the *option* loop index instead
of the *question* index:

```jinja
{# before — every option became its own radio group #}
{% for q in qs %}
  {% for opt in q.options %}
    <input type="radio" name="{{ topic }}__{{ loop.index0 }}">
```

`app.py` reads `request.form.get(f"{topic}__{i}")` where `i` is the question
index, so it never received a usable answer. Options were also not submitting
their own index as a value. Fixed by capturing the outer loop:

```jinja
{% for q in qs %}
  {% set qi = loop.index0 %}
  {% for opt in q.options %}
    <input type="radio" name="{{ topic }}__{{ qi }}" value="{{ loop.index0 }}">
```

**`topic.html`** — the same mistake in the "Quick Check" self-test
(`name="answer_{{ loop.index0 }}_group"`), fixed the same way.

Verified by submitting a fully correct assessment (Git & GitHub → 5 topics
mastered, 100%) and a fully incorrect one (Databases & SQL → 0 mastered, 0%).
Before the fix, neither registered.

---

## 6. Design system

The application pages inherit the landing page's tokens rather than
approximating them:

- **Type** — Space Grotesk for headings, DM Sans for body (Google Fonts).
- **Colour** — `--ink #17213f`, `--muted #6f7c9d`, `--blue #4778f5`,
  `--purple #8067e8`, `--green #25bda5` on a `#f7f9ff` field.
- **Surfaces** — 18–24 px radii, `rgba(249,251,255,.92)` cards, soft
  blue-tinted shadows, pill buttons, frosted-glass navigation.
- **Motion** — the same `driftA/B/C`, `cardIn`, `formIn` and `footerGradient`
  keyframes, plus the `IntersectionObserver` scroll reveal, and a
  `prefers-reduced-motion` escape hatch.

Old variable names (`--text-dim`, `--accent`) are aliased to the new palette,
so any inline `var()` left in a template still resolves.

Layout-wise, the logged-in app uses the landing's `app-dashboard` grid —
sidebar / main / right rail — which collapses to two columns under 1150 px and
to a slide-in drawer under 760 px. Pages without a right rail get `.no-right`
automatically.

---

## 7. Testing

A 71-check end-to-end pass over the running server covered: landing render,
login/register/forgot-password, the full register → assessment → roadmap →
topic → self-test loop, the search / chatbot / transcript / playlist-jump JSON
APIs, the admin student list, student detail and research pages, and
access-control redirects for anonymous and non-admin users. All passed.

`instance/skillgappath.db` ships with its original contents — the accounts
created during testing were discarded.
