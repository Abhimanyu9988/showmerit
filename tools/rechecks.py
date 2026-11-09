"""Copy the lab recheck results into data/rechecks.json, for build.py to show on each article.

The pipeline repo saves them on its public analytics branch (see its docs/rechecks.md). Only fields that fit their
expected form are kept, and each run link must be a run of that repo, so the page never shows text or links from
anywhere else. If the fetch fails, the saved file stays as it was.
"""
import json
import os
import pathlib
import re
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = "https://api.github.com/repos/Abhimanyu9988/Abhimanyu9988.github.io/contents/analytics/rechecks.json?ref=analytics"
RUN = re.compile(r"https://github\.com/Abhimanyu9988/Abhimanyu9988\.github\.io/actions/runs/\d+")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
SLUG = re.compile(r"[a-z0-9-]{1,120}")
WORD = re.compile(r"[A-Za-z0-9][\w .+-]{0,59}")


def versions(found):
    if not isinstance(found, dict):
        return None
    out = {k: v for k, v in list(found.items())[:12] if isinstance(k, str) and isinstance(v, str) and WORD.fullmatch(k) and WORD.fullmatch(v)}
    return out if len(out) == len(found) else None


def dated(found):
    return isinstance(found, dict) and isinstance(found.get("date"), str) and DATE.fullmatch(found["date"]) \
        and isinstance(found.get("run"), str) and RUN.fullmatch(found["run"])


def clean(data):
    """The results with anything unexpected left out. A record that doesn't fit is dropped whole, so no line shows."""
    out = {}
    for slug, record in ((data or {}).get("articles") or {}).items():
        if not SLUG.fullmatch(str(slug)) or not isinstance(record, dict):
            continue
        kept = {}
        free = record.get("free")
        if dated(free):
            results = []
            for r in free.get("results") or []:
                vs = versions(r.get("versions")) if isinstance(r, dict) else None
                if vs is None or r.get("set") not in ("article", "newest") or not isinstance(r.get("passed"), bool):
                    results = None
                    break
                results.append({"set": r["set"], "versions": vs, "passed": r["passed"]})
            if results is not None:
                kept["free"] = {"date": free["date"], "run": free["run"], "results": results,
                                "newest_is_article": free.get("newest_is_article") is True}
        aws = record.get("aws")
        if dated(aws) and versions(aws.get("versions")) is not None and isinstance(aws.get("passed"), bool):
            kept["aws"] = {"date": aws["date"], "run": aws["run"], "versions": versions(aws["versions"]), "passed": aws["passed"]}
        if kept:
            out[slug] = kept
    return {"articles": out}


def refresh():
    headers = {"User-Agent": "showmerit", "Accept": "application/vnd.github.raw+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    with urllib.request.urlopen(urllib.request.Request(SOURCE, headers=headers), timeout=30) as response:
        found = clean(json.load(response))
    (ROOT / "data/rechecks.json").write_text(json.dumps(found, indent=1, sort_keys=True) + "\n")
    print(f"Rechecks: {len(found['articles'])} articles")
