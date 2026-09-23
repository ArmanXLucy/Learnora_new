"""
YouTube video lookup for a given topic, across multiple content creators
so learners can pick whichever teaching style suits them.

Two paths, both embedding directly on the site (no external tab needed):
1. Flagship videos: a small set of individually verified real freeCodeCamp
   video IDs (see data/curriculum.json -> flagship_videos), guaranteed to
   embed correctly without any API key.
2. Live YouTube Data API v3 search (if YOUTUBE_API_KEY is configured):
   dynamic, per-topic, per-creator embedded results.

If neither is available for a given skill/topic, we fall back to a
same-shaped "open on YouTube" card rather than a broken embed.

Transcript + translation: uses YouTube's public timedtext endpoint to fetch
(and, via the tlang parameter, auto-translate) a video's caption track, so
the transcript can be displayed directly on the page below the video. This
is a best-effort feature (depends on the video having captions available
and on YouTube's endpoint being reachable) with graceful fallback if not.
"""
import re
import xml.etree.ElementTree as ET

import requests
from ml.skill_graph import CREATORS, FLAGSHIP_VIDEOS, estimate_topic_start_seconds

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
TIMEDTEXT_LIST_URL = "https://video.google.com/timedtext"


def get_videos_for_topic(skill_id, topic_id, topic_display, keywords, api_key, max_creators=5):
    """Returns a list of video entries. The first entry is always a guaranteed
    embed (flagship video for the skill, or live API result) when possible."""
    query = f"{topic_display} tutorial {keywords}".strip()
    creators = CREATORS[:max_creators]
    results = []

    flagship = FLAGSHIP_VIDEOS.get(skill_id)
    if flagship:
        start_seconds = estimate_topic_start_seconds(skill_id, topic_id)
        results.append({
            "creator": flagship["creator"],
            "mode": "embed",
            "video_id": flagship["video_id"],
            "start_seconds": start_seconds,
            "is_estimate": start_seconds > 0,
            "title": f"{flagship['title']} (full course — jumped to an estimated position for \"{topic_display}\"; use the player's chapter list or seek bar to fine-tune)" if start_seconds > 0 else flagship["title"],
            "url": f"https://www.youtube.com/watch?v={flagship['video_id']}",
        })

    if not api_key:
        for c in creators:
            if flagship and c["name"] == flagship["creator"]:
                continue
            results.append({
                "creator": c["name"],
                "mode": "search_link",
                "url": f"https://www.youtube.com/results?search_query={requests.utils.quote(c['name'] + ' ' + query)}",
                "video_id": None,
                "title": f"Search \"{query}\" on {c['name']} (add a YOUTUBE_API_KEY in .env for live embedded results from every creator)",
            })
        return results

    for c in creators:
        try:
            params = {
                "part": "snippet",
                "q": f"{c['name']} {query}",
                "type": "video",
                "maxResults": 1,
                "key": api_key,
            }
            resp = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=6)
            data = resp.json()
            items = data.get("items", [])
            if items:
                item = items[0]
                results.append({
                    "creator": c["name"],
                    "mode": "embed",
                    "video_id": item["id"]["videoId"],
                    "title": item["snippet"]["title"],
                    "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                })
            else:
                results.append({
                    "creator": c["name"], "mode": "search_link", "video_id": None,
                    "url": f"https://www.youtube.com/results?search_query={requests.utils.quote(c['name'] + ' ' + query)}",
                    "title": f"No direct match found — search '{query}' on {c['name']}",
                })
        except Exception:
            results.append({
                "creator": c["name"], "mode": "search_link", "video_id": None,
                "url": f"https://www.youtube.com/results?search_query={requests.utils.quote(c['name'] + ' ' + query)}",
                "title": f"Search '{query}' on {c['name']} (live lookup failed, showing search link)",
            })
    return results


def get_playlist_jump(playlist_id, topic_display, keywords, api_key):
    """
    Best-effort: find the video within a real playlist that best matches the
    current topic, so playback can start there instead of from video 1.
    Requires a YouTube Data API key (free quota) to list playlist items —
    without one, returns None and the caller should embed the playlist from
    the start, relying on YouTube's own in-player playlist panel for manual
    navigation.
    """
    if not api_key or not playlist_id:
        return None
    try:
        items = []
        page_token = None
        for _ in range(3):  # up to ~150 items, plenty for a course playlist
            params = {
                "part": "snippet", "playlistId": playlist_id,
                "maxResults": 50, "key": api_key,
            }
            if page_token:
                params["pageToken"] = page_token
            resp = requests.get("https://www.googleapis.com/youtube/v3/playlistItems", params=params, timeout=8)
            data = resp.json()
            items.extend(data.get("items", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break

        if not items:
            return None

        query_words = set((topic_display + " " + keywords).lower().replace("/", " ").split())
        best_score, best_item, best_index = 0, None, 0
        for i, item in enumerate(items):
            title = item["snippet"]["title"].lower()
            score = sum(1 for w in query_words if len(w) > 2 and w in title)
            if score > best_score:
                best_score, best_item, best_index = score, item, i

        if best_item and best_score > 0:
            video_id = best_item["snippet"]["resourceId"]["videoId"]
            return {"video_id": video_id, "title": best_item["snippet"]["title"], "index": best_index}
        return None
    except Exception:
        return None


def get_docs_links(topic_display, keywords):
    """Curated 'blogs & docs' links generated from the topic — points to
    reliable open reference sites rather than scraping/guessing article URLs."""
    q = requests.utils.quote(f"{topic_display} {keywords}")
    return [
        {"label": "MDN Web Docs", "url": f"https://developer.mozilla.org/en-US/search?q={q}", "blurb": "Official, precise reference docs — best for exact syntax and behavior."},
        {"label": "freeCodeCamp News", "url": f"https://www.freecodecamp.org/news/search/?query={q}", "blurb": "Friendly, example-heavy written tutorials and explainer articles."},
        {"label": "GeeksforGeeks", "url": f"https://www.geeksforgeeks.org/?s={q}", "blurb": "Good for practice problems, diagrams, and interview-style explanations."},
        {"label": "Stack Overflow", "url": f"https://stackoverflow.com/search?q={q}", "blurb": "Real questions and answers from other learners hitting the same issue."},
    ]


# ------------------------------------------------------- transcript/translate
LANGUAGES = [
    ("en", "English"), ("hi", "Hindi"), ("bn", "Bengali"), ("es", "Spanish"),
    ("fr", "French"), ("de", "German"), ("zh-Hans", "Chinese (Simplified)"),
    ("ar", "Arabic"), ("pt", "Portuguese"), ("ru", "Russian"), ("ja", "Japanese"),
    ("ta", "Tamil"), ("te", "Telugu"), ("mr", "Marathi"), ("ur", "Urdu"),
]


def _clean_caption_text(raw):
    text = re.sub(r"<[^>]+>", "", raw)
    return (text.replace("&amp;", "&").replace("&#39;", "'")
            .replace("&quot;", '"').replace("\n", " ").strip())


def get_transcript(video_id, target_lang="en"):
    """
    Best-effort transcript fetch + translate using YouTube's public timedtext
    endpoint (no API key required). Returns {ok, lines: [{start, text}], error}.
    This depends on the video having captions/auto-captions available and on
    YouTube's endpoint responding — if either fails, ok=False with a message,
    and the caller should fall back to YouTube's own on-player CC translation.
    """
    try:
        list_resp = requests.get(TIMEDTEXT_LIST_URL, params={"type": "list", "v": video_id}, timeout=6)
        if list_resp.status_code != 200 or not list_resp.text.strip():
            return {"ok": False, "lines": [], "error": "No caption tracks are available for this video."}

        root = ET.fromstring(list_resp.text)
        tracks = root.findall("track")
        if not tracks:
            return {"ok": False, "lines": [], "error": "No caption tracks are available for this video."}

        source_lang = tracks[0].get("lang_code", "en")
        for t in tracks:
            if t.get("lang_code", "").startswith("en"):
                source_lang = t.get("lang_code")
                break

        params = {"v": video_id, "lang": source_lang}
        if target_lang and target_lang != source_lang:
            params["tlang"] = target_lang

        cap_resp = requests.get(TIMEDTEXT_LIST_URL, params=params, timeout=8)
        if cap_resp.status_code != 200 or not cap_resp.text.strip():
            return {"ok": False, "lines": [], "error": "Captions could not be retrieved (YouTube may be rate-limiting this request)."}

        cap_root = ET.fromstring(cap_resp.text)
        lines = []
        for node in cap_root.findall("text"):
            start = float(node.get("start", 0))
            text = _clean_caption_text(node.text or "")
            if text:
                lines.append({"start": round(start, 1), "text": text})

        if not lines:
            return {"ok": False, "lines": [], "error": "Captions were empty for this video."}
        return {"ok": True, "lines": lines, "error": None}
    except Exception as e:
        return {"ok": False, "lines": [], "error": f"Transcript fetch failed ({type(e).__name__}). Use the player's own CC/gear icon instead."}
