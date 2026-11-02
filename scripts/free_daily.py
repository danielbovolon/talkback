#!/usr/bin/env python3
"""Free daily edition for Talkback, run by GitHub Actions (no AI, no paid services).

1. If today's day brief (data/briefs/day-YYYY-MM-DD.json) is missing, build one from
   the news feeds of the sources in FEEDS: title, date, link and the outlet's own summary.
2. If today's lesson (data/learn/YYYY-MM-DD.json) is missing, pick a lesson and a
   9-question quiz from the bank in data/bank/ (lessons.json, questions.json),
   rotating so lessons and questions don't repeat for as long as possible.

Files that already exist (for example written by a Claude run) are never touched.
Only the Python standard library is used.
"""
import datetime, email.utils, hashlib, html, json, pathlib, random, re, sys, urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TZ = ZoneInfo("Europe/Rome")
NOW = datetime.datetime.now(TZ)
TODAY = NOW.date()
KEY = TODAY.isoformat()
LABEL = TODAY.strftime("%a ") + str(TODAY.day) + TODAY.strftime(" %b %Y")

# (source name, feed URL, default category, priority 1-3)
FEEDS = [
    ("Sound On Sound", "https://www.soundonsound.com/latest_news.xml", "gear", 3),
    ("Production Expert", "https://www.production-expert.com/production-expert-1?format=rss", "post", 3),
    ("ProSoundWeb", "https://www.prosoundweb.com/feed/", "live", 3),
    ("FOH", "https://fohonline.com/feed/", "live", 2),
    ("TPi", "https://www.tpimagazine.com/feed/", "live", 2),
    ("TV Technology", "https://www.tvtechnology.com/feeds.xml", "live", 2),
    ("A Sound Effect", "https://feeds.feedburner.com/ASoundEffect", "post", 2),
    ("Newsshooter (audio)", "https://www.newsshooter.com/category/audio/feed/", "post", 2),
    ("CineD", "https://www.cined.com/feed/", "post", 1),
    ("Gearnews", "https://www.gearnews.com/feed/", "gear", 2),
    ("MusicRadar", "https://www.musicradar.com/feeds.xml", "gear", 1),
    ("Sonicstate", "https://feeds.feedburner.com/SonicstatecomNews", "instruments", 2),
    ("Synthtopia", "https://www.synthtopia.com/feed/", "instruments", 1),
    ("Synth Anatomy", "https://synthanatomy.com/feed/", "instruments", 1),
    ("CDM", "https://cdm.link/feed/", "software", 2),
    ("Bedroom Producers Blog", "https://bedroomproducersblog.com/feed/", "plugins", 2),
    ("Hearing Review", "https://hearingreview.com/feed", "hearing", 2),
    ("ScienceDaily (acoustics)", "https://www.sciencedaily.com/rss/matter_energy/acoustics.xml", "science", 3),
    ("ScienceDaily (hearing)", "https://www.sciencedaily.com/rss/health_medicine/hearing_loss.xml", "hearing", 3),
    ("Music Business Worldwide", "https://www.musicbusinessworldwide.com/feed/", "industry", 1),
    ("Digital Music News", "https://www.digitalmusicnews.com/feed/", "industry", 1),
]

# First matching rule wins; checked against title + summary.
RULES = [
    ("hearing", r"\b(hearing|tinnitus|cochlear|deaf|audiolog|earplug|ear protection|noise[- ]induced)"),
    ("ai", r"\b(AI|A\.I\.|artificial intelligence|machine learning|generative|Suno|Udio|ElevenLabs|neural)\b"),
    ("games", r"\b(game audio|video game|Wwise|FMOD|Unreal|Unity|MetaSounds|VR|AR)\b"),
    ("post", r"\b(Atmos|post[- ]production|dialogue|ADR|Foley|location sound|re-recording|mixing stage|immersive|loudness|R128|lavalier|lav\b|timecode)"),
    ("live", r"\b(console|line array|PA system|loudspeaker system|wireless|IEM|in-ear|Dante|AES67|Milan|tour|festival|FOH|monitor engineer|broadcast|intercom)"),
    ("plugins", r"\b(plug-?in|VST|AU\b|AAX|CLAP)"),
    ("software", r"\b(DAW|Pro Tools|Logic Pro|Cubase|Nuendo|REAPER|Ableton|Bitwig|Studio One|Resolve|Fairlight|update|firmware|macOS|Windows)"),
    ("instruments", r"\b(synth|synthesizer|Eurorack|drum machine|sampler|sequencer|keyboard|modular)"),
    ("speakers", r"\b(monitors?|headphones?|speakers?|subwoofer|loudspeaker|driver)\b"),
    ("gear", r"\b(microphone|mic\b|mics\b|preamp|interface|converter|recorder|compressor|equaliser|equalizer|outboard)"),
    ("science", r"\b(study|research|researchers|scientists|university|journal)\b"),
    ("industry", r"\b(acquire|acquisition|lawsuit|court|royalt|copyright|layoffs|revenue|NAMM|AES|IBC|ISE|Superbooth)"),
]
SKIP = re.compile(r"\b(deal|deals|sale|% off|Black Friday|Cyber Monday|discount|giveaway|win a|guitar pedal|best .* to buy|buyer'?s guide)\b", re.I)
FREE = re.compile(r"\bfree\b", re.I)

def text(el, *names):
    for n in names:
        x = el.find(n)
        if x is not None and (x.text or "").strip():
            return x.text.strip()
        if x is not None and x.get("href"):
            return x.get("href")
    return ""

def clean(s):
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*(The post .* appeared first on .*|Read more.*|Continue reading.*)$", "", s)
    if len(s) > 300:
        cut = s[:300]
        end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
        s = cut[: end + 1] if end > 120 else cut.rsplit(" ", 1)[0] + "…"
    return s

def parse_date(s):
    if not s: return None
    try:
        d = email.utils.parsedate_to_datetime(s)
    except Exception:
        try: d = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception: return None
    if d.tzinfo is None: d = d.replace(tzinfo=datetime.timezone.utc)
    return d.astimezone(TZ)

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (TalkbackFreeEdition; +https://talkback.danielbovolon.com)"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()

def items_from(xml):
    root = ET.fromstring(xml)
    for el in root.iter():
        if el.tag.endswith("}entry"): el.tag = "entry"
        elif "}" in el.tag: el.tag = el.tag.split("}", 1)[1]
    for it in list(root.iter("item")) + list(root.iter("entry")):
        yield {
            "title": clean(text(it, "title")),
            "url": text(it, "link", "guid").strip(),
            "date": parse_date(text(it, "pubDate", "published", "updated", "date")),
            "summary": clean(text(it, "description", "summary", "encoded", "content")),
        }

def categorise(title, summary, default):
    blob = title + " " + summary
    for cat, rx in RULES:
        if re.search(rx, title, re.I if cat not in ("ai", "games") else 0): return cat
    for cat, rx in RULES:
        if re.search(rx, blob, re.I if cat not in ("ai", "games") else 0): return cat
    return default

def recent_urls(days=4):
    seen = set()
    for p in sorted((DATA / "briefs").glob("day-*.json"))[-days:]:
        try: seen |= {i.get("url") for i in json.loads(p.read_text())["items"]}
        except Exception: pass
    return seen

def least_recent(pool, used_key, history):
    """Pick the entry used longest ago (never used first); ties keep bank order."""
    last = {}
    for day, k in history: last[k] = day
    return sorted(pool, key=lambda x: last.get(used_key(x), ""))[0]

def build_brief():
    out = DATA / "briefs" / f"day-{KEY}.json"
    if out.exists():
        print(f"{out.name} exists, leaving it"); return
    hours = 72 if TODAY.weekday() == 0 else 48
    since = NOW - datetime.timedelta(hours=hours)
    seen, found, used_sources = recent_urls(), [], []
    for name, url, default, prio in FEEDS:
        try:
            got = list(items_from(fetch(url)))
        except Exception as e:
            print(f"skip {name}: {e}", file=sys.stderr); continue
        n = 0
        for it in got:
            if not it["title"] or not it["url"].startswith("http") or it["url"] in seen: continue
            if not it["date"] or it["date"] < since or it["date"] > NOW + datetime.timedelta(hours=2): continue
            if SKIP.search(it["title"]): continue
            seen.add(it["url"])
            cat = categorise(it["title"], it["summary"], default)
            entry = {"cat": cat, "signal": 1, "auto": True, "date": it["date"].date().isoformat(),
                     "title": it["title"], "take": it["summary"], "source": name, "url": it["url"]}
            if FREE.search(it["title"]): entry["free"] = True
            found.append((prio, it["date"], n, entry)); n += 1
        if n: used_sources.append(name)
    # Up to 4 per source, round-robin by source priority, then newest first.
    found = [f for f in found if f[2] < 4]
    found.sort(key=lambda f: (f[2], -f[0], -f[1].timestamp()))
    items = [f[3] for f in found[:30]]
    if not items:
        print("no feed items found; not writing a brief", file=sys.stderr); return
    for it in items[:6]:
        it["signal"] = 2
    craft_bank = json.loads((DATA / "bank" / "craft.json").read_text())
    hist = []
    for p in sorted((DATA / "briefs").glob("day-*.json")):
        try:
            c = json.loads(p.read_text()).get("craft") or {}
            if c.get("title"): hist.append((p.stem, c["title"]))
        except Exception: pass
    craft = least_recent(craft_bank, lambda c: c["title"], hist) if craft_bank else None
    srcs = ", ".join(used_sources[:5]) + (f" and {len(used_sources) - 5} more" if len(used_sources) > 5 else "")
    start = (NOW - datetime.timedelta(hours=hours)).date()
    rng = f"{start.day} {start.strftime('%b')} – {TODAY.day} {TODAY.strftime('%b %Y')}"
    doc = {"period": "day", "key": KEY, "label": LABEL, "range": rng,
           "generated": NOW.isoformat(timespec="seconds"), "auto": True,
           "headline": "Today's sound headlines",
           "lead": f"{len(items)} new stories from {len(used_sources)} sound and audio news sources over the last {hours} hours, including {srcs}. "
                   "This edition is assembled automatically from the outlets' own feeds: titles and summaries are theirs, sorted into sections. Open a story for the full article.",
           "items": items}
    if craft: doc["craft"] = craft
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out.name}: {len(items)} items from {len(used_sources)} sources")

def build_learn():
    out = DATA / "learn" / f"{KEY}.json"
    if out.exists():
        print(f"{out.name} exists, leaving it"); return
    lessons = json.loads((DATA / "bank" / "lessons.json").read_text())
    questions = json.loads((DATA / "bank" / "questions.json").read_text())
    past = []
    for p in sorted((DATA / "learn").glob("*.json")):
        try: past.append((p.stem, json.loads(p.read_text())))
        except Exception: pass
    hist = [(day, d.get("lesson", {}).get("title")) for day, d in past]
    last_topic = past[-1][1].get("lesson", {}).get("topic") if past else None
    pool = [l for l in lessons if l.get("topic") != last_topic] or lessons
    lesson = least_recent(pool, lambda l: l["title"], hist)

    recent = set()
    for day, d in past[-30:]:
        recent |= {q["q"] for q in d.get("quiz", {}).get("questions", [])}
    rnd = random.Random(int(hashlib.sha256(KEY.encode()).hexdigest(), 16))
    own = [q for q in questions if q.get("lesson") == lesson["id"]]
    others = [q for q in questions if q.get("lesson") != lesson["id"]]
    rnd.shuffle(own); rnd.shuffle(others)
    fresh = lambda qs: sorted(qs, key=lambda q: q["q"] in recent)  # unseen first, order otherwise kept
    want_own = {"advanced": 2, "intermediate": 1, "basic": 1}
    picked = []
    for lvl in ("advanced", "intermediate", "basic"):
        chosen = [q for q in fresh(own) if q["level"] == lvl][: want_own[lvl]]
        topics = {q.get("topic") for q in chosen}
        for q in fresh(others):
            if len(chosen) == 3: break
            if q["level"] != lvl or q in chosen: continue
            if q.get("topic") in topics and any(o["level"] == lvl and o.get("topic") not in topics and o not in chosen for o in others):
                continue
            chosen.append(q); topics.add(q.get("topic"))
        for q in fresh(others):  # fallback if topic spreading left gaps
            if len(chosen) == 3: break
            if q["level"] == lvl and q not in chosen: chosen.append(q)
        picked += chosen
    if len(picked) != 9:
        sys.exit("question bank too small for a 9-question quiz")
    qs = [{k: q[k] for k in ("level", "topic", "q", "options", "answer", "explain") if k in q} for q in picked]
    L = {k: v for k, v in lesson.items() if k != "id"}
    doc = {"key": KEY, "label": LABEL, "generated": NOW.isoformat(timespec="seconds"), "auto": True,
           "lesson": L, "quiz": {"questions": qs}}
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out.name}: lesson '{L['title']}'")

if __name__ == "__main__":
    (DATA / "briefs").mkdir(parents=True, exist_ok=True)
    (DATA / "learn").mkdir(parents=True, exist_ok=True)
    build_learn()
    build_brief()
