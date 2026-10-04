#!/usr/bin/env python3
"""Rebuild data/index.json from the brief and lesson files.

Run after adding or changing files in data/briefs or data/learn:
    python3 scripts/build_index.py
It also validates every file, and keeps only the newest 60 day briefs
and 120 lessons in the index (older files stay in the repo).
"""
import json, pathlib, sys, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CATS = {"gear","speakers","instruments","plugins","software","post","live","games",
        "science","hearing","tech","industry","ai","craft"}

def load(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        sys.exit(f"Invalid JSON in {p}: {e}")

def check_brief(p, d):
    for k in ("period","key","label","headline","items"):
        if k not in d: sys.exit(f"{p.name}: missing '{k}'")
    for i, it in enumerate(d["items"]):
        for k in ("cat","title","url"):
            if k not in it: sys.exit(f"{p.name}: item {i} missing '{k}'")
        if it["cat"] not in CATS: print(f"warning: {p.name} item {i} has unknown category '{it['cat']}'")

def check_learn(p, d):
    qs = d.get("quiz", {}).get("questions", [])
    if len(qs) != 9: sys.exit(f"{p.name}: quiz must have 9 questions, has {len(qs)}")
    for i, q in enumerate(qs):
        if len(q.get("options", [])) != 4 or not (0 <= q.get("answer", -1) <= 3):
            sys.exit(f"{p.name}: question {i+1} needs 4 options and an answer index 0-3")

briefs, days = [], []
for p in sorted((DATA / "briefs").glob("*.json")):
    d = load(p); check_brief(p, d)
    (days if d["period"] == "day" else briefs).append(p.name)
days = sorted(days, reverse=True)[:60]
lessons = []
for p in sorted((DATA / "learn").glob("*.json"), reverse=True)[:120]:
    d = load(p); check_learn(p, d); lessons.append(p.name)

index = {"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
         "briefs": days + sorted(briefs, reverse=True), "learn": lessons}
(DATA / "index.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
print(f"index.json: {len(days)} day briefs, {len(briefs)} other briefs, {len(lessons)} lessons")
