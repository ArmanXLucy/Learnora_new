import difflib
import random
import re
import os
import uuid
import json
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify

from config import Config
import dal
from firebase_auth import verify_id_token
from youtube import get_videos_for_topic, get_docs_links, get_transcript, get_playlist_jump, LANGUAGES

from ml.skill_graph import SKILLS, TOPIC_META, build_roadmap, COLD_START_QUESTIONS, PLAYLISTS
from ml.cold_start import score_quiz, get_quiz_questions
from ml.recommend import recommend
from ml.completion_model import predict_completion_probability
from ml.chatbot import get_response as chatbot_response
from ml import evaluate as evaluate_module
from ml.openrouter_learning import general_plan, analyze_syllabus, generate_diagnostic, classify_level

app = Flask(__name__)
app.config.from_object(Config)
app.config.setdefault("MAX_CONTENT_LENGTH", 4 * 1024 * 1024)
ALLOWED_AVATAR_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


# ---------------------------------------------------------------- helpers --
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin access required.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def current_user():
    uid = session.get("user_id")
    return dal.get_user_by_id(uid) if uid else None


def skill_level_normalized(mastered_set):
    if not mastered_set:
        return 0.1
    diffs = [TOPIC_META[t]["difficulty"] for t in mastered_set]
    return min(1.0, max(diffs) / 5.0)


# ---------------------------------------------------------------- landing --
@app.route("/")
def intro():
    """Public Learnora landing page. The skill catalogue is rendered straight
    from the same skill graph the logged-in product uses, so the marketing page
    and the roadmaps can never drift apart."""
    preview_skills = list(SKILLS.items())[:3]
    return render_template(
        "landing.html",
        skills=SKILLS,
        preview_skills=preview_skills,
        year=datetime.now().year,
    )


# ------------------------------------------------------------------- auth --
@app.route("/login", methods=["GET", "POST"])
def login():
    # User authentication is handled by Firebase in the browser. The POST
    # endpoint below exchanges a verified Firebase ID token for a Flask session.
    return render_template("login.html", firebase_config={
        "apiKey": Config.FIREBASE_API_KEY,
        "authDomain": Config.FIREBASE_AUTH_DOMAIN,
        "projectId": Config.FIREBASE_PROJECT_ID,
        "storageBucket": Config.FIREBASE_STORAGE_BUCKET,
        "messagingSenderId": Config.FIREBASE_MESSAGING_SENDER_ID,
        "appId": Config.FIREBASE_APP_ID,
    })


@app.route("/auth/firebase-session", methods=["POST"])
def firebase_session():
    data = request.get_json(silent=True) or {}
    id_token = data.get("idToken", "")
    profile = data.get("profile") or {}

    if not id_token:
        return jsonify({"ok": False, "error": "Missing Firebase ID token."}), 400

    try:
        decoded = verify_id_token(id_token)
    except Exception as exc:
        app.logger.exception("Firebase ID token verification failed")
        # Keep credentials/token details out of the response, but return a
        # useful configuration hint for development and Vercel logs.
        if app.debug or os.environ.get("VERCEL") != "1":
            return jsonify({
                "ok": False,
                "error": f"Firebase token verification failed: {exc}"
            }), 401
        return jsonify({
            "ok": False,
            "error": "Invalid or expired Firebase authentication token."
        }), 401

    firebase_uid = decoded.get("uid")
    email = (decoded.get("email") or profile.get("email") or "").strip().lower()
    if not firebase_uid or not email:
        return jsonify({"ok": False, "error": "Firebase account must have an email address."}), 400

    # Enforce Firebase email ownership on the server as well as in the browser.
    # This prevents an unverified account from creating a Learnora session by
    # calling this endpoint directly.
    if not decoded.get("email_verified", False):
        return jsonify({
            "ok": False,
            "error": "Please verify your email address before accessing Learnora."
        }), 403

    user = dal.get_user_by_firebase_uid(firebase_uid)

    # Allow existing Learnora accounts to be linked automatically by email.
    if user is None:
        user = dal.get_user_by_email(email)
        if user is not None:
            dal.attach_firebase_uid(user["id"], firebase_uid)
            user = dal.get_user_by_id(user["id"])

    if user is None:
        name = (profile.get("name") or decoded.get("name") or email.split("@")[0]).strip()
        username = (profile.get("username") or email.split("@")[0]).strip().lower()
        username = re.sub(r"[^a-z0-9_]", "", username)[:20] or "learner"
        if not USERNAME_PATTERN.match(username) or dal.get_user_by_username(username):
            base = username[:16] or "learner"
            username = base
            suffix = 1
            while dal.get_user_by_username(username):
                username = f"{base}{suffix}"[:20]
                suffix += 1

        age = profile.get("age") or None
        profession = (profile.get("profession") or "").strip()
        phone = (profile.get("phone") or "").strip()
        location = (profile.get("location") or "India").strip() or "India"
        user_id = dal.create_firebase_user(name, age, profession, phone, username, email, location, firebase_uid)
        user = dal.get_user_by_id(user_id)

    session.clear()
    session["user_id"] = user["id"]
    session["is_admin"] = False
    session["firebase_uid"] = firebase_uid
    dal.record_activity(user["id"])
    return jsonify({"ok": True, "redirect": url_for("dashboard")})


@app.route("/admin-login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""
    if username == Config.ADMIN_USERNAME.lower() and password == Config.ADMIN_PASSWORD:
        session.clear()
        session["is_admin"] = True
        session["admin_username"] = username
        return jsonify({"ok": True, "redirect": url_for("admin_dashboard")})
    return jsonify({"ok": False, "error": "Invalid admin credentials."}), 401


NAME_PATTERN = re.compile(r"^[A-Za-z ]{2,50}$")
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,20}$")
PHONE_PATTERN = re.compile(r"^[0-9]{7,15}$")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Registration is completed by Firebase JS; this route remains GET-only
        # for compatibility with existing links.
        return redirect(url_for("register"))

    return render_template("register.html", firebase_config={
        "apiKey": Config.FIREBASE_API_KEY,
        "authDomain": Config.FIREBASE_AUTH_DOMAIN,
        "projectId": Config.FIREBASE_PROJECT_ID,
        "storageBucket": Config.FIREBASE_STORAGE_BUCKET,
        "messagingSenderId": Config.FIREBASE_MESSAGING_SENDER_ID,
        "appId": Config.FIREBASE_APP_ID,
    })


@app.route("/forgot-password")
def forgot_password():
    return render_template("forgot_password.html", firebase_config={
        "apiKey": Config.FIREBASE_API_KEY,
        "authDomain": Config.FIREBASE_AUTH_DOMAIN,
        "projectId": Config.FIREBASE_PROJECT_ID,
        "storageBucket": Config.FIREBASE_STORAGE_BUCKET,
        "messagingSenderId": Config.FIREBASE_MESSAGING_SENDER_ID,
        "appId": Config.FIREBASE_APP_ID,
    })


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()
    if user is None:
        session.pop("user_id", None)
        return redirect(url_for("login"))
    prefs = dal.get_or_create_preferences(user["id"])
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        age = request.form.get("age") or None
        profession = request.form.get("profession", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip().lower()
        location = request.form.get("location", "India").strip() or "India"
        if not NAME_PATTERN.match(name):
            flash("Name can only contain letters and spaces.", "danger")
            return redirect(url_for("profile"))
        if phone and not PHONE_PATTERN.match(phone):
            flash("Phone number must be 7-15 digits.", "danger")
            return redirect(url_for("profile"))
        try:
            hours = int(request.form.get("hours_per_week", 5))
        except ValueError:
            hours = 5
        hours = max(1, min(30, hours))

        # Optional profile photo upload. The existing photo is retained unless a new one is supplied.
        avatar = request.files.get("avatar")
        if avatar and avatar.filename:
            original = secure_filename(avatar.filename)
            ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
            if ext not in ALLOWED_AVATAR_EXTENSIONS:
                flash("Profile photo must be PNG, JPG, JPEG, WEBP, or GIF.", "danger")
                return redirect(url_for("profile"))
            upload_dir = os.path.join(app.root_path, "static", "uploads", "avatars")
            os.makedirs(upload_dir, exist_ok=True)
            filename = f"user_{user['id']}_{uuid.uuid4().hex}.{ext}"
            path = os.path.join(upload_dir, filename)
            avatar.save(path)
            dal.update_avatar(user["id"], f"uploads/avatars/{filename}")

        dal.update_profile(user["id"], name, age, profession, phone, email, location)
        dal.update_learning_preferences(user["id"], request.form.get("learning_goal", "").strip(), hours, request.form.get("learning_style", "mixed"), request.form.get("learning_focus", "").strip())

        security_question = request.form.get("security_question", "").strip()
        security_answer = request.form.get("security_answer", "").strip()
        if security_question:
            dal.update_security_details(user["id"], security_question, security_answer or None)

        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html", user=user, prefs=prefs)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user = current_user()
    if user is None:
        session.pop("user_id", None)
        return redirect(url_for("login"))
    prefs = dal.get_or_create_preferences(user["id"])
    if request.method == "POST":
        dal.update_settings(user["id"], request.form.get("theme", "system"), "reminders" in request.form, "streak_alerts" in request.form, "product_updates" in request.form, "auto_next" in request.form, "show_completed" in request.form)
        flash("Settings saved.", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html", user=user, prefs=prefs)


@app.route("/help", methods=["GET", "POST"])
@login_required
def helpdesk():
    user = current_user()
    if user is None:
        session.pop("user_id", None)
        return redirect(url_for("login"))
    if request.method == "POST":
        topic = request.form.get("topic", "General help").strip()
        message = request.form.get("message", "").strip()
        if not message:
            flash("Please describe your question before sending it.", "danger")
            return redirect(url_for("helpdesk"))
        dal.create_support_ticket(user["id"], topic, message)
        flash("Your question has been sent to the Learnora help desk.", "success")
        return redirect(url_for("helpdesk"))
    return render_template("help.html", user=user)


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("intro"))


# -------------------------------------------------------------- dashboard --
@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()

    # The session may contain an old user_id after a database reset,
    # deleted account, or expired/invalid login session. Never attempt
    # to access user["id"] when the user record cannot be found.
    if user is None:
        session.pop("user_id", None)
        session["is_admin"] = False
        flash("Your session has expired. Please log in again.", "warning")
        return redirect(url_for("login"))

    enrollments = dal.get_enrollments_for_user(user["id"])
    skill_progress = []
    next_up = []
    total_mastered = 0
    total_topics_all = 0

    for e in enrollments:
        mastered = dal.get_mastered_set(user["id"], e["skill_id"])
        total_topics = len(SKILLS[e["skill_id"]]["topics"])
        pct = round(100 * len(mastered) / total_topics) if total_topics else 0
        total_mastered += len(mastered)
        total_topics_all += total_topics
        skill_progress.append({
            "skill_id": e["skill_id"],
            "display_name": SKILLS[e["skill_id"]]["display_name"],
            "percent": pct,
            "mastered_count": len(mastered),
            "total_topics": total_topics,
        })

        # first couple of unlocked-but-unmastered topics, for the "Up Next" rail
        for t in build_roadmap(e["skill_id"], mastered):
            if t["status"] == "ready" and len(next_up) < 4:
                next_up.append({
                    "skill_id": e["skill_id"],
                    "skill_name": SKILLS[e["skill_id"]]["display_name"],
                    "display": t["display"],
                })
                break

    streak = dal.get_streak_info(user["id"])

    # last seven days as a Mon..Sun style activity strip
    active_dates = set(streak["active_dates"])
    today = datetime.now().date()
    week_activity = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        week_activity.append({
            "label": day.strftime("%a")[0],
            "date": day.isoformat(),
            "active": day.isoformat() in active_dates,
        })

    overall_percent = round(100 * total_mastered / total_topics_all) if total_topics_all else 0

    return render_template("dashboard.html", user=user, skill_progress=skill_progress,
                            all_skills=SKILLS, streak=streak,
                            week_activity=week_activity, overall_percent=overall_percent,
                            total_mastered=total_mastered, total_topics=total_topics_all,
                            next_up=next_up)


@app.route("/my-skills")
@login_required
def my_skills():
    user = current_user()
    if user is None:
        session.pop("user_id", None)
        return redirect(url_for("login"))
    enrollments = dal.get_enrollments_for_user(user["id"])
    skills = []
    for e in enrollments:
        meta = SKILLS[e["skill_id"]]
        mastered = dal.get_mastered_set(user["id"], e["skill_id"])
        total = len(meta["topics"])
        pct = round(100 * len(mastered) / total) if total else 0
        skills.append({
            "skill_id": e["skill_id"],
            "display_name": meta["display_name"],
            "description": meta.get("description", ""),
            "mastered": len(mastered),
            "total": total,
            "percent": pct,
        })
    return render_template("my_skills.html", user=user, skills=skills)


@app.route("/roadmaps")
@login_required
def roadmaps():
    user = current_user()
    if user is None:
        session.pop("user_id", None)
        return redirect(url_for("login"))

    enrolled = []
    for e in dal.get_enrollments_for_user(user["id"]):
        sid = e["skill_id"]
        meta = SKILLS.get(sid)
        if not meta:
            continue
        mastered = dal.get_mastered_set(user["id"], sid)
        road = build_roadmap(sid, mastered)
        level = (e["level"] or "basic").lower()
        threshold = {"basic": 1, "intermediate": 2, "advanced": 3}.get(level, 1)
        road = [t for t in road if t["difficulty"] >= threshold]
        total_hours = sum(float(t.get("hours", 0)) for t in road)
        completed_hours = sum(float(t.get("hours", 0)) for t in road if t.get("status") == "mastered")
        remaining_hours = max(0.0, total_hours - completed_hours)
        hours_week = max(1, int(e["hours_per_week"] or 5))
        remaining_weeks = (remaining_hours / hours_week) if hours_week else 0
        ready = next((t for t in road if t.get("status") == "ready"), None)
        enrolled.append({
            "skill_id": sid,
            "display_name": meta["display_name"],
            "description": meta.get("description", ""),
            "percent": round(100 * len(mastered) / len(meta["topics"])) if meta["topics"] else 0,
            "mastered": len(mastered),
            "total": len(meta["topics"]),
            "hours_week": hours_week,
            "total_hours": total_hours,
            "remaining_hours": remaining_hours,
            "remaining_weeks": remaining_weeks,
            "next_topic": ready["display"] if ready else None,
        })
    return render_template("roadmaps.html", user=user, enrolled=enrolled)


@app.route("/assessments")
@login_required
def assessments():
    user = current_user()
    if user is None:
        session.pop("user_id", None)
        return redirect(url_for("login"))
    enrollments = dal.get_enrollments_for_user(user["id"])
    enrolled_ids = {e["skill_id"] for e in enrollments}
    return render_template("assessments.html", user=user, all_skills=SKILLS, enrolled_ids=enrolled_ids, TOPIC_META=TOPIC_META)


@app.route("/api/search-skills")
@login_required
def api_search_skills():
    q = request.args.get("q", "").strip().lower()
    results = []
    if not q:
        for sid, meta in SKILLS.items():
            results.append({"id": sid, "name": meta["display_name"], "description": meta["description"]})
        return jsonify(results)

    for sid, meta in SKILLS.items():
        name = meta["display_name"].lower()
        aliases = [a.lower() for a in meta.get("aliases", [])]
        score = 0
        if q == sid or q in name or name.startswith(q):
            score = 3
        elif any(q == a or q in a or a.startswith(q) for a in aliases):
            score = 3
        elif any(word.startswith(q) for word in name.split()):
            score = 2
        elif difflib.SequenceMatcher(None, q, name).ratio() > 0.45:
            score = 1
        else:
            # broaden the match to topics inside the skill, e.g. "py" surfacing
            # Data Science because it contains a "Python for Data Science" topic.
            # Match on whole words / word-prefixes only (not bare substrings),
            # so short queries like "os" don't spuriously match "micrOServices"
            # or "repOSitories" inside unrelated topics.
            for topic_id in meta["topics"]:
                t_words = TOPIC_META[topic_id]["display"].lower().replace("&", " ").replace("/", " ").split()
                if any(w == q or w.startswith(q) for w in t_words) and len(q) >= 2:
                    score = 1
                    break
        if score:
            results.append({"id": sid, "name": meta["display_name"], "description": meta["description"], "_score": score})

    results.sort(key=lambda r: r.pop("_score"), reverse=True)
    return jsonify(results)


# ------------------------------------------------------- adaptive learning --
@app.route("/skill/<skill_id>/start", methods=["GET", "POST"])
@login_required
def start_skill(skill_id):
    if skill_id not in SKILLS:
        flash("Unknown skill.", "danger")
        return redirect(url_for("dashboard"))

    user = current_user()
    existing = dal.get_enrollment(user["id"], skill_id)
    if existing and request.args.get("reset") != "1":
        return redirect(url_for("roadmap", skill_id=skill_id))

    if request.method == "POST":
        try:
            hours = max(1, min(40, int(request.form.get("hours_per_week", 5))))
        except (TypeError, ValueError):
            hours = 5

        mode = request.form.get("syllabus_mode", "general")
        source = "general"
        syllabus_name = "General Learnora syllabus"
        saved_file = None
        try:
            if mode == "general":
                plan = general_plan(skill_id)
            elif mode == "text":
                syllabus_text = (request.form.get("syllabus_text") or "").strip()
                if len(syllabus_text) < 30:
                    flash("Please paste at least a short syllabus before continuing.", "warning")
                    return redirect(url_for("start_skill", skill_id=skill_id))
                source = "text"
                syllabus_name = "Pasted syllabus"
                plan = analyze_syllabus(skill_id, text=syllabus_text)
            elif mode == "file":
                upload = request.files.get("syllabus_file")
                if not upload or not upload.filename:
                    flash("Choose a JPG, JPEG, PNG, PDF, TXT, MD or DOCX syllabus file.", "warning")
                    return redirect(url_for("start_skill", skill_id=skill_id))
                ext = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
                allowed = {"jpg", "jpeg", "png", "pdf", "txt", "md", "docx"}
                if ext not in allowed:
                    flash("Supported syllabus formats: JPG, JPEG, PNG, PDF, TXT, MD and DOCX.", "danger")
                    return redirect(url_for("start_skill", skill_id=skill_id))
                # Uploaded syllabi only need temporary local storage while
                # the AI parser reads them. Vercel's deployed filesystem is
                # read-only, so never persist the upload under instance/.
                import tempfile
                filename = f"{user['id']}_{uuid.uuid4().hex}.{ext}"
                temp_file = tempfile.NamedTemporaryFile(
                    mode="wb", suffix=f".{ext}", delete=False
                )
                try:
                    upload.save(temp_file)
                    temp_file.close()
                    saved_file = temp_file.name
                    source = "file"
                    syllabus_name = secure_filename(upload.filename)
                    plan = analyze_syllabus(skill_id, file_path=saved_file)
                    try:
                        os.remove(saved_file)
                    except OSError:
                        pass
                    saved_file = None
                finally:
                    try:
                        temp_file.close()
                    except Exception:
                        pass
            else:
                flash("Choose a syllabus option.", "warning")
                return redirect(url_for("start_skill", skill_id=skill_id))

            selected_ids = [t for t in plan.get("selected_topic_ids", []) if t in SKILLS[skill_id]["topics"]]
            if not selected_ids:
                selected_ids = list(SKILLS[skill_id]["topics"])
            plan["selected_topic_ids"] = selected_ids
            plan_json = json.dumps(plan, ensure_ascii=False)
            if existing:
                dal.update_enrollment_plan(user["id"], skill_id, hours, source, syllabus_name,
                                           plan.get("summary", ""), plan_json)
            else:
                dal.create_enrollment(user["id"], skill_id, hours, source, syllabus_name,
                                      plan.get("summary", ""), plan_json)
            dal.record_activity(user["id"])
            return redirect(url_for("syllabus_preview", skill_id=skill_id))
        except Exception as exc:
            if saved_file and os.path.exists(saved_file):
                try:
                    os.remove(saved_file)
                except OSError:
                    pass
            flash(str(exc), "danger")
            return redirect(url_for("start_skill", skill_id=skill_id))

    return render_template("start_skill.html", skill_id=skill_id, skill=SKILLS[skill_id], user=user)


@app.route("/skill/<skill_id>/syllabus-preview")
@login_required
def syllabus_preview(skill_id):
    if skill_id not in SKILLS:
        return redirect(url_for("dashboard"))
    user = current_user()
    enrollment = dal.get_enrollment(user["id"], skill_id)
    if not enrollment:
        return redirect(url_for("start_skill", skill_id=skill_id))
    try:
        plan = json.loads(enrollment["roadmap_json"] or "{}")
    except Exception:
        plan = general_plan(skill_id)
    selected = set(plan.get("selected_topic_ids", SKILLS[skill_id]["topics"]))
    ordered_ids = [r.get("topic_id") for r in plan.get("roadmap", []) if r.get("topic_id") in selected]
    ordered_ids += [t for t in SKILLS[skill_id]["topics"] if t in selected and t not in ordered_ids]
    roadmap = []
    for idx, topic_id in enumerate(ordered_ids, start=1):
        meta = TOPIC_META[topic_id]
        roadmap.append({"topic_id": topic_id, "display": meta["display"], "difficulty": meta["difficulty"], "hours": meta["hours"], "keywords": meta["keywords"], "priority": idx})
    return render_template("syllabus_preview.html", user=user, skill=SKILLS[skill_id], skill_id=skill_id,
                           enrollment=enrollment, plan=plan, roadmap=roadmap)


@app.route("/skill/<skill_id>/quiz", methods=["GET", "POST"])
@login_required
def quiz(skill_id):
    if skill_id not in SKILLS:
        return redirect(url_for("dashboard"))
    user = current_user()
    enrollment = dal.get_enrollment(user["id"], skill_id)
    if not enrollment:
        return redirect(url_for("start_skill", skill_id=skill_id))

    try:
        plan = json.loads(enrollment["roadmap_json"] or "{}")
    except Exception:
        plan = general_plan(skill_id)
    topic_ids = [t for t in plan.get("selected_topic_ids", SKILLS[skill_id]["topics"]) if t in SKILLS[skill_id]["topics"]]

    if request.method == "POST":
        try:
            questions = json.loads(enrollment["diagnostic_json"] or "[]")
        except Exception:
            questions = []
        if not questions:
            flash("The assessment expired. Please start it again.", "warning")
            return redirect(url_for("syllabus_preview", skill_id=skill_id))
        answers = {}
        for q in questions:
            raw = request.form.get(f"q_{q['id']}")
            answers[str(q["id"])] = int(raw) if raw is not None and raw.isdigit() else -1
        result = classify_level(questions, answers)
        level = result["level"]
        dal.update_enrollment_level(user["id"], skill_id, level, result.get("score", 0), result.get("reason", ""))

        # Treat content below the detected level as already known. This is what
        # prevents an intermediate/advanced learner from being sent through the
        # basic curriculum again.
        dal.clear_level_baseline(user["id"], skill_id)
        threshold = {"basic": 1, "intermediate": 2, "advanced": 3}[level]
        for topic_id in topic_ids:
            if TOPIC_META[topic_id]["difficulty"] < threshold:
                dal.upsert_topic_progress(user["id"], skill_id, topic_id, True, 1.0, "level_baseline")

        # Record the diagnostic score for every tested topic so later roadmap
        # recommendations can use the learner's actual answers.
        for q in questions:
            correct = answers.get(str(q["id"]), -1) == q["answer"]
            dal.upsert_topic_progress(user["id"], skill_id, q["topic_id"], correct, 1.0 if correct else 0.0, "diagnostic")
        dal.record_activity(user["id"])
        flash(f"Assessment complete. Learnora placed you at {level.title()} level and skipped content below that level.", "success")
        return redirect(url_for("roadmap", skill_id=skill_id))

    try:
        questions = json.loads(enrollment["diagnostic_json"] or "[]")
    except Exception:
        questions = []
    if not questions:
        try:
            questions = generate_diagnostic(skill_id, topic_ids, enrollment["syllabus_summary"] or plan.get("summary", ""))
            dal.update_enrollment_diagnostic(user["id"], skill_id, json.dumps(questions, ensure_ascii=False))
        except Exception as exc:
            flash(str(exc), "danger")
            return redirect(url_for("syllabus_preview", skill_id=skill_id))

    safe_questions = [
        {
            "id": q["id"],
            "set_number": q.get("set_number", 1),
            "set_title": q.get("set_title", "Foundation"),
            "topic_id": q["topic_id"],
            "difficulty": q["difficulty"],
            "question": q["question"],
            "options": q["options"],
        }
        for q in questions
    ]
    return render_template("quiz.html", skill_id=skill_id, skill=SKILLS[skill_id], questions=safe_questions,
                           hours_per_week=enrollment["hours_per_week"], enrollment=enrollment)


# --------------------------------------------------------------- roadmap --
@app.route("/skill/<skill_id>/roadmap")
@login_required
def roadmap(skill_id):
    if skill_id not in SKILLS:
        return redirect(url_for("dashboard"))
    user = current_user()
    enrollment = dal.get_enrollment(user["id"], skill_id)
    if not enrollment:
        return redirect(url_for("start_skill", skill_id=skill_id))

    try:
        plan = json.loads(enrollment["roadmap_json"] or "{}")
    except Exception:
        plan = general_plan(skill_id)
    selected = set(plan.get("selected_topic_ids", SKILLS[skill_id]["topics"]))
    mastered = dal.get_mastered_set(user["id"], skill_id)
    all_road = build_roadmap(skill_id, mastered)
    road = [r for r in all_road if r["topic_id"] in selected]

    # Enforce the level gate even if a user has old progress from an earlier
    # assessment. Intermediate/advanced learners never receive lower-level
    # lessons in their active roadmap; lower levels are treated as baseline knowledge.
    level = (enrollment["level"] or "basic").lower()
    threshold = {"basic": 1, "intermediate": 2, "advanced": 3}.get(level, 1)
    road = [r for r in road if r["difficulty"] >= threshold]

    recs = recommend(skill_id, mastered, hours_per_week=enrollment["hours_per_week"], top_k=5)
    recs = [r for r in recs if r["topic_id"] in {x["topic_id"] for x in road}]

    level_norm = skill_level_normalized(mastered)
    for r in recs:
        diff_norm = r["difficulty"] / 5.0
        prereq_ready = 1 if r["status"] == "ready" else 0
        r["ai_match"] = round(predict_completion_probability(level_norm, diff_norm, prereq_ready) * 100, 1)

    return render_template("roadmap.html", skill_id=skill_id, skill=SKILLS[skill_id], roadmap=road,
                           recommendations=recs, hours_per_week=enrollment["hours_per_week"],
                           enrollment=enrollment, plan=plan)


# ----------------------------------------------------------------- topic --
@app.route("/skill/<skill_id>/topic/<topic_id>", methods=["GET", "POST"])
@login_required
def topic_page(skill_id, topic_id):
    if skill_id not in SKILLS or topic_id not in TOPIC_META:
        return redirect(url_for("dashboard"))
    user = current_user()
    meta = TOPIC_META[topic_id]
    enrollment = dal.get_enrollment(user["id"], skill_id)
    if enrollment:
        level = (enrollment["level"] or "basic").lower()
        threshold = {"basic": 1, "intermediate": 2, "advanced": 3}.get(level, 1)
        if meta["difficulty"] < threshold:
            flash(f"{meta['display']} is below your detected {level.title()} level, so Learnora has already skipped it.", "info")
            return redirect(url_for("roadmap", skill_id=skill_id))

    if request.method == "POST":
        bank = COLD_START_QUESTIONS.get(topic_id, [])
        selected_idx = [int(i) for i in request.form.getlist("qidx")]
        selected_ans = [int(a) for a in request.form.getlist("answer")]
        correct = 0
        for qi, ans in zip(selected_idx, selected_ans):
            if qi < len(bank) and bank[qi]["answer"] == ans:
                correct += 1
        frac = correct / len(selected_idx) if selected_idx else 0
        mastered = frac >= 0.6

        dal.upsert_topic_progress(user["id"], skill_id, topic_id, mastered, frac, "post_video_test")
        dal.record_activity(user["id"])

        if mastered:
            flash(f"Nice work! You've mastered {meta['display']}.", "success")
        else:
            flash(f"You scored {round(frac*100)}% — review the videos below and try again when ready.", "warning")
        return redirect(url_for("roadmap", skill_id=skill_id))

    videos = get_videos_for_topic(skill_id, topic_id, meta["display"], meta["keywords"], app.config.get("YOUTUBE_API_KEY"))
    docs = get_docs_links(meta["display"], meta["keywords"])
    playlists = PLAYLISTS.get(skill_id, [])

    bank = COLD_START_QUESTIONS.get(topic_id, [])
    test_questions = random.sample(bank, min(3, len(bank))) if bank else []
    test_questions_indexed = [{"idx": bank.index(q), "q": q["q"], "options": q["options"]} for q in test_questions]

    return render_template("topic.html", skill_id=skill_id, skill=SKILLS[skill_id],
                            topic_id=topic_id, meta=meta, videos=videos, docs=docs,
                            test_questions=test_questions_indexed, languages=LANGUAGES,
                            playlists=playlists)


@app.route("/api/playlist-jump")
@login_required
def api_playlist_jump():
    playlist_id = request.args.get("playlist_id", "")
    topic_id = request.args.get("topic_id", "")
    meta = TOPIC_META.get(topic_id)
    if not playlist_id or not meta:
        return jsonify({"ok": False, "video_id": None})
    result = get_playlist_jump(playlist_id, meta["display"], meta["keywords"], app.config.get("YOUTUBE_API_KEY"))
    if result:
        return jsonify({"ok": True, **result})
    return jsonify({"ok": False, "video_id": None})


@app.route("/api/transcript")
@login_required
def api_transcript():
    video_id = request.args.get("video_id", "")
    lang = request.args.get("lang", "en")
    if not video_id:
        return jsonify({"ok": False, "lines": [], "error": "Missing video_id"}), 400
    result = get_transcript(video_id, lang)
    return jsonify(result)


# --------------------------------------------------------------- chatbot --
@app.route("/api/chatbot", methods=["POST"])
@login_required
def api_chatbot():
    data = request.get_json(force=True) or {}
    message = data.get("message", "")
    current_topic = data.get("topic")
    reply = chatbot_response(message, current_topic=current_topic)
    return jsonify({"reply": reply})


# ----------------------------------------------------------------- admin --
@app.route("/admin")
@admin_required
def admin_dashboard():
    users = dal.get_all_users(exclude_admin=True)
    student_rows = []
    for u in users:
        enrollments = dal.get_enrollments_for_user(u["id"])
        skills_summary = []
        for e in enrollments:
            mastered = dal.get_mastered_set(u["id"], e["skill_id"])
            total = len(SKILLS[e["skill_id"]]["topics"])
            skills_summary.append(f"{SKILLS[e['skill_id']]['display_name']} ({len(mastered)}/{total})")
        student_rows.append({"user": u, "skills_summary": skills_summary, "num_skills": len(enrollments)})
    return render_template("admin_dashboard.html", student_rows=student_rows)


@app.route("/admin/student/<int:user_id>")
@admin_required
def admin_student_detail(user_id):
    user = dal.get_user_by_id(user_id)
    if not user:
        flash("Student not found.", "danger")
        return redirect(url_for("admin_dashboard"))
    enrollments = dal.get_enrollments_for_user(user["id"])
    details = []
    for e in enrollments:
        mastered = dal.get_mastered_set(user["id"], e["skill_id"])
        road = build_roadmap(e["skill_id"], mastered)
        progress_rows = dal.get_all_topic_progress(user["id"], e["skill_id"])
        details.append({
            "skill_id": e["skill_id"],
            "display_name": SKILLS[e["skill_id"]]["display_name"],
            "hours_per_week": e["hours_per_week"],
            "roadmap": road,
            "progress_rows": progress_rows,
        })
    streak = dal.get_streak_info(user["id"])
    return render_template("admin_student.html", user=user, details=details, streak=streak)


@app.route("/admin/research")
@admin_required
def admin_research():
    metrics = evaluate_module.load_last_metrics()
    return render_template("admin_research.html", metrics=metrics, skills=SKILLS)


@app.route("/admin/research/run", methods=["POST"])
@admin_required
def admin_research_run():
    evaluate_module.run_full_evaluation()
    flash("Evaluation complete. Metrics and graphs updated below.", "success")
    return redirect(url_for("admin_research"))


# ------------------------------------------------------------- filters ----
@app.template_filter("dt")
def format_datetime(value, fmt="%d %b %Y %H:%M"):
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).strftime(fmt)
    except (TypeError, ValueError):
        return str(value)


# ------------------------------------------------------------------- run --
# Firestore is initialized lazily by firebase_auth.py/dal.py. There is no
# SQLite bootstrap because Vercel's deployment filesystem is read-only.

if __name__ == "__main__":
    app.run(debug=True, port=5000)
