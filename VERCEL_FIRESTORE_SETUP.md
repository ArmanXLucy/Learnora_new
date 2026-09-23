# Learnora — Vercel + Firebase + Firestore

This version removes SQLite as the persistent application database. Learnora
stores users, preferences, enrollments, diagnostic results, topic progress,
streaks, and support tickets in Cloud Firestore.

## 1. Firebase

Open Firebase Console and select your Learnora project.

Enable:
- Authentication -> Email/Password
- Firestore Database

Under Project Settings -> Service accounts -> Firebase Admin SDK, generate a
private key if you need a local service-account file.

## 2. Local development

Keep `serviceAccountKey.json` in the project root (never commit it).

Create `.env` from `.env.example` and set:

    FIREBASE_PROJECT_ID=learnora-6a2ab
    FIREBASE_SERVICE_ACCOUNT_PATH=serviceAccountKey.json

Also set the Firebase Web config and your OpenRouter key.

The backend resolves a relative service-account path relative to the project
directory, so it does not depend on the current working directory.

Run:

    pip install -r requirements.txt
    python app.py

## 3. Vercel

Do NOT upload `.env`, `serviceAccountKey.json`, or the SQLite database.

Add these Production environment variables in Vercel:

    SECRET_KEY
    ADMIN_USERNAME
    ADMIN_PASSWORD

    FIREBASE_API_KEY
    FIREBASE_AUTH_DOMAIN
    FIREBASE_PROJECT_ID
    FIREBASE_STORAGE_BUCKET
    FIREBASE_MESSAGING_SENDER_ID
    FIREBASE_APP_ID

    FIREBASE_SERVICE_ACCOUNT_JSON

    OPENROUTER_API_KEY
    OPENROUTER_MODEL

`FIREBASE_SERVICE_ACCOUNT_JSON` must contain the complete service-account
JSON from the SAME Firebase project as `FIREBASE_PROJECT_ID`.

For this project the expected project ID is:

    learnora-6a2ab

After changing environment variables, redeploy the project.

## 4. Firebase login flow

The browser signs in with Firebase Authentication and requests a fresh ID
token with `getIdToken(true)`. Flask verifies that token with the Firebase
Admin SDK and then creates the Learnora session.

If token verification fails, Vercel logs contain the server-side exception
without exposing credentials to the browser.

## 5. Syllabus files on Vercel

Uploaded syllabus files are stored temporarily under the runtime temporary
directory only while the AI parser reads them. They are not persisted to the
read-only Vercel application filesystem.

## 6. Existing SQLite data

This version does not automatically migrate an old SQLite database into
Firestore. Existing local users/progress in `instance/skillgappath.db` remain
local. New Firebase users and application data are written to Firestore.
