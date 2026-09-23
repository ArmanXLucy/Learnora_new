"""
Learnora Firestore Data Access Layer.

Persistent application data is stored in Cloud Firestore so the app can run
correctly on Vercel/serverless environments.

Authentication configuration:
- Production/Vercel: FIREBASE_SERVICE_ACCOUNT_JSON
- Local development: FIREBASE_SERVICE_ACCOUNT_PATH=serviceAccountKey.json
"""
from datetime import datetime, timedelta, timezone

from firebase_admin import firestore
from werkzeug.security import generate_password_hash, check_password_hash

from firebase_auth import get_firebase_app


_firestore = None


def _get_firestore():
    """Return a Firestore client using the shared Firebase Admin app."""
    global _firestore
    if _firestore is None:
        _firestore = firestore.client(get_firebase_app())
    return _firestore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now():
    """UTC timestamp string, compatible with the previous SQLite DAL."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def today():
    """Current UTC date string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _doc_data(snapshot):
    """Convert a Firestore document snapshot to the dict shape used by app.py."""
    if snapshot is None or not snapshot.exists:
        return None

    data = snapshot.to_dict() or {}
    data["id"] = snapshot.id
    return data


def _query_first(query):
    docs = list(query.limit(1).stream())
    return _doc_data(docs[0]) if docs else None


def _user_ref(user_id):
    return _get_firestore().collection("users").document(str(user_id))


def _preference_ref(user_id):
    return _get_firestore().collection("user_preferences").document(str(user_id))


def _enrollment_ref(user_id, skill_id):
    return (
        _get_firestore()
        .collection("enrollments")
        .document(f"{user_id}__{skill_id}")
    )


def _topic_progress_ref(user_id, skill_id, topic_id, source):
    key = f"{user_id}__{skill_id}__{topic_id}__{source}"
    # Firestore document IDs cannot contain "/" safely for this use.
    key = key.replace("/", "_")
    return _get_firestore().collection("topic_progress").document(key)


def _activity_ref(user_id, activity_date):
    return (
        _get_firestore()
        .collection("activity_log")
        .document(f"{user_id}__{activity_date}")
    )


# ------------------------------------------------------------------ users ---

def create_user(
    name, age, profession, phone, username, email, location, password,
    security_question=None, security_answer=None
):
    db = _get_firestore()
    pw_hash = generate_password_hash(password)
    answer_hash = (
        generate_password_hash(security_answer.strip().lower())
        if security_answer else None
    )

    doc_ref = db.collection("users").document()
    data = {
        "name": name,
        "age": age,
        "profession": profession,
        "phone": phone,
        "username": username,
        "email": email,
        "email_normalized": (email or "").strip().lower(),
        "location": location,
        "password_hash": pw_hash,
        "security_question": security_question,
        "security_answer_hash": answer_hash,
        "firebase_uid": None,
        "avatar_path": "",
        "is_admin": False,
        "created_at": now(),
    }
    doc_ref.set(data)
    return doc_ref.id


def get_user_by_firebase_uid(firebase_uid):
    db = _get_firestore()
    return _query_first(
        db.collection("users")
        .where("firebase_uid", "==", firebase_uid)
    )


def get_user_by_email(email):
    db = _get_firestore()
    normalized = (email or "").strip().lower()

    # New Firestore users have email_normalized. The second query keeps this
    # compatible with documents created before this field was introduced.
    user = _query_first(
        db.collection("users")
        .where("email_normalized", "==", normalized)
    )
    if user:
        return user

    return _query_first(
        db.collection("users")
        .where("email", "==", email)
    )


def create_firebase_user(
    name, age, profession, phone, username, email, location, firebase_uid
):
    db = _get_firestore()

    doc_ref = db.collection("users").document()
    doc_ref.set({
        "name": name,
        "age": age,
        "profession": profession,
        "phone": phone,
        "username": username,
        "email": email,
        "email_normalized": (email or "").strip().lower(),
        "location": location,
        "password_hash": "",
        "security_question": None,
        "security_answer_hash": None,
        "firebase_uid": firebase_uid,
        "avatar_path": "",
        "is_admin": False,
        "created_at": now(),
    })
    return doc_ref.id


def attach_firebase_uid(user_id, firebase_uid):
    _user_ref(user_id).set(
        {"firebase_uid": firebase_uid},
        merge=True,
    )


def get_user_by_username(username):
    db = _get_firestore()
    return _query_first(
        db.collection("users").where("username", "==", username)
    )


def get_user_by_id(user_id):
    return _doc_data(_user_ref(user_id).get())


def check_user_password(user_row, password):
    password_hash = user_row.get("password_hash", "")
    return bool(password_hash) and check_password_hash(password_hash, password)


def check_security_answer(user_row, answer):
    answer_hash = user_row.get("security_answer_hash")
    if not answer_hash:
        return False
    return check_password_hash(answer_hash, answer.strip().lower())


def update_password(user_id, new_password):
    _user_ref(user_id).set(
        {"password_hash": generate_password_hash(new_password)},
        merge=True,
    )


def get_or_create_preferences(user_id):
    ref = _preference_ref(user_id)
    snapshot = ref.get()

    if not snapshot.exists:
        ref.set({
            "user_id": str(user_id),
            "theme": "light",
            "reminders": True,
            "streak_alerts": True,
            "product_updates": True,
            "auto_next": True,
            "show_completed": True,
            "learning_goal": "",
            "hours_per_week": 0,
            "learning_style": "",
            "learning_focus": "",
        })
        snapshot = ref.get()

    data = snapshot.to_dict() or {}
    data["id"] = snapshot.id
    return data


def update_avatar(user_id, avatar_path):
    _user_ref(user_id).set({"avatar_path": avatar_path}, merge=True)


def update_security_details(user_id, security_question, security_answer=None):
    data = {"security_question": security_question}
    if security_answer:
        data["security_answer_hash"] = generate_password_hash(
            security_answer.strip().lower()
        )
    _user_ref(user_id).set(data, merge=True)


def update_profile(user_id, name, age, profession, phone, email, location):
    _user_ref(user_id).set({
        "name": name,
        "age": age,
        "profession": profession,
        "phone": phone,
        "email": email,
        "email_normalized": (email or "").strip().lower(),
        "location": location,
    }, merge=True)


def update_learning_preferences(
    user_id, learning_goal, hours_per_week, learning_style, learning_focus
):
    _preference_ref(user_id).set({
        "user_id": str(user_id),
        "learning_goal": learning_goal,
        "hours_per_week": hours_per_week,
        "learning_style": learning_style,
        "learning_focus": learning_focus,
    }, merge=True)


def update_settings(
    user_id, theme, reminders, streak_alerts,
    product_updates, auto_next, show_completed
):
    _preference_ref(user_id).set({
        "user_id": str(user_id),
        "theme": theme,
        "reminders": bool(reminders),
        "streak_alerts": bool(streak_alerts),
        "product_updates": bool(product_updates),
        "auto_next": bool(auto_next),
        "show_completed": bool(show_completed),
    }, merge=True)


def create_support_ticket(user_id, topic, message):
    ref = _get_firestore().collection("support_tickets").document()
    ref.set({
        "user_id": str(user_id),
        "topic": topic,
        "message": message,
        "created_at": now(),
    })
    return ref.id


def get_all_users(exclude_admin=True):
    db = _get_firestore()
    query = db.collection("users")

    if exclude_admin:
        query = query.where("is_admin", "==", False)

    docs = list(query.stream())
    rows = [_doc_data(doc) for doc in docs]
    rows.sort(key=lambda row: row.get("created_at", ""), reverse=True)
    return rows


# ------------------------------------------------------------- enrollment ----

def create_enrollment(
    user_id, skill_id, hours_per_week,
    syllabus_source="general", syllabus_name="",
    syllabus_summary="", roadmap_json="[]"
):
    ref = _enrollment_ref(user_id, skill_id)
    ref.set({
        "user_id": str(user_id),
        "skill_id": skill_id,
        "started_at": now(),
        "hours_per_week": hours_per_week,
        "syllabus_source": syllabus_source,
        "syllabus_name": syllabus_name,
        "syllabus_summary": syllabus_summary,
        "roadmap_json": roadmap_json,
        "diagnostic_json": "[]",
        "level": "basic",
        "level_score": 0,
        "level_reason": "",
    })


def update_enrollment_diagnostic(user_id, skill_id, diagnostic_json):
    _enrollment_ref(user_id, skill_id).set(
        {"diagnostic_json": diagnostic_json},
        merge=True,
    )


def update_enrollment_level(user_id, skill_id, level, score, reason=""):
    _enrollment_ref(user_id, skill_id).set({
        "level": level,
        "level_score": score,
        "level_reason": reason,
    }, merge=True)


def update_enrollment_plan(
    user_id, skill_id, hours_per_week,
    syllabus_source, syllabus_name, syllabus_summary, roadmap_json
):
    _enrollment_ref(user_id, skill_id).set({
        "hours_per_week": hours_per_week,
        "syllabus_source": syllabus_source,
        "syllabus_name": syllabus_name,
        "syllabus_summary": syllabus_summary,
        "roadmap_json": roadmap_json,
        "diagnostic_json": "[]",
        "level": "basic",
        "level_score": 0,
        "level_reason": "",
    }, merge=True)


def clear_level_baseline(user_id, skill_id):
    db = _get_firestore()
    docs = (
        db.collection("topic_progress")
        .where("user_id", "==", str(user_id))
        .where("skill_id", "==", skill_id)
        .where("source", "==", "level_baseline")
        .stream()
    )

    batch = db.batch()
    count = 0
    for doc in docs:
        batch.delete(doc.reference)
        count += 1

    if count:
        batch.commit()


def get_enrollment(user_id, skill_id):
    return _doc_data(_enrollment_ref(user_id, skill_id).get())


def get_enrollments_for_user(user_id):
    db = _get_firestore()
    docs = (
        db.collection("enrollments")
        .where("user_id", "==", str(user_id))
        .stream()
    )
    return [_doc_data(doc) for doc in docs]


# ---------------------------------------------------------- topic progress --

def delete_topic_progress_by_source(user_id, skill_id, source):
    db = _get_firestore()
    docs = (
        db.collection("topic_progress")
        .where("user_id", "==", str(user_id))
        .where("skill_id", "==", skill_id)
        .where("source", "==", source)
        .stream()
    )

    batch = db.batch()
    count = 0
    for doc in docs:
        batch.delete(doc.reference)
        count += 1

    if count:
        batch.commit()


def add_topic_progress(
    user_id, skill_id, topic_id, mastered, quiz_score, source
):
    ref = _topic_progress_ref(user_id, skill_id, topic_id, source)
    ref.set({
        "user_id": str(user_id),
        "skill_id": skill_id,
        "topic_id": topic_id,
        "mastered": int(mastered),
        "quiz_score": quiz_score,
        "source": source,
        "updated_at": now(),
    })


def get_topic_progress_row(user_id, skill_id, topic_id, source):
    ref = _topic_progress_ref(user_id, skill_id, topic_id, source)
    return _doc_data(ref.get())


def upsert_topic_progress(
    user_id, skill_id, topic_id, mastered, quiz_score, source
):
    ref = _topic_progress_ref(user_id, skill_id, topic_id, source)
    ref.set({
        "user_id": str(user_id),
        "skill_id": skill_id,
        "topic_id": topic_id,
        "mastered": int(mastered),
        "quiz_score": quiz_score,
        "source": source,
        "updated_at": now(),
    }, merge=True)


def get_mastered_set(user_id, skill_id):
    db = _get_firestore()
    docs = (
        db.collection("topic_progress")
        .where("user_id", "==", str(user_id))
        .where("skill_id", "==", skill_id)
        .where("mastered", "==", 1)
        .stream()
    )
    return {
        doc.to_dict().get("topic_id")
        for doc in docs
        if doc.to_dict().get("topic_id") is not None
    }


def get_all_topic_progress(user_id, skill_id):
    db = _get_firestore()
    docs = (
        db.collection("topic_progress")
        .where("user_id", "==", str(user_id))
        .where("skill_id", "==", skill_id)
        .stream()
    )
    rows = [_doc_data(doc) for doc in docs]
    rows.sort(key=lambda row: row.get("updated_at", ""), reverse=True)
    return rows


# -------------------------------------------------------------- streaks ----

def record_activity(user_id):
    """Mark today as an active day for this learner (idempotent)."""
    ref = _activity_ref(user_id, today())
    ref.set({
        "user_id": str(user_id),
        "activity_date": today(),
    }, merge=True)


def get_streak_info(user_id):
    """Return current/longest streak and recent active dates."""
    db = _get_firestore()
    docs = (
        db.collection("activity_log")
        .where("user_id", "==", str(user_id))
        .stream()
    )

    dates = {
        doc.to_dict().get("activity_date")
        for doc in docs
        if doc.to_dict().get("activity_date")
    }

    if not dates:
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "active_dates": [],
            "total_active_days": 0,
        }

    date_objs = sorted(
        (datetime.strptime(d, "%Y-%m-%d") for d in dates),
        reverse=True,
    )

    current_streak = 0
    cursor = datetime.strptime(today(), "%Y-%m-%d")

    date_set = set(date_objs)

    if cursor not in date_set:
        cursor -= timedelta(days=1)

    while cursor in date_set:
        current_streak += 1
        cursor -= timedelta(days=1)

    all_sorted = sorted(date_objs)
    longest_streak = 1
    run = 1

    for i in range(1, len(all_sorted)):
        if (all_sorted[i] - all_sorted[i - 1]).days == 1:
            run += 1
            longest_streak = max(longest_streak, run)
        else:
            run = 1

    last_84 = sorted(dates)[-84:]

    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "active_dates": last_84,
        "total_active_days": len(dates),
    }
