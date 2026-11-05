"""Refresh public data. If a source fails, its saved data stays as it was and the other source still runs."""
import json
import os
import pathlib
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
profile = json.loads((ROOT / "data/profile.json").read_text())


def fetch(url, headers=None):
    request = urllib.request.Request(url, headers={"User-Agent": "showmerit", **(headers or {})})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def github():
    user = profile["github"]
    query = urllib.parse.quote(f"author:{user} is:pr is:merged -user:{user}")
    found = fetch(f"https://api.github.com/search/issues?q={query}&per_page=100&sort=updated",
                  {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"})
    if found.get("incomplete_results") or not found.get("items"):
        raise ValueError("incomplete result")
    rows = [{"date": item["closed_at"][:10], "repo": item["repository_url"].split("/repos/")[1],
             "number": item["number"], "title": item["title"], "url": item["html_url"]} for item in found["items"]]
    rows.sort(key=lambda row: (row["date"], row["number"]), reverse=True)
    (ROOT / "data/contributions.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
    print(f"GitHub: {len(rows)} merged pull requests")


def credly():
    badges, page = [], 1
    while True:
        found = fetch(f"https://www.credly.com/users/{profile['credly']}/badges.json?page={page}", {"Accept": "application/json"})
        badges += found["data"]
        if page >= found["metadata"]["total_pages"]:
            break
        page += 1
    rows = []
    for badge in badges:
        if badge.get("state") != "accepted" or badge.get("public") is False:
            continue
        template = badge["badge_template"]
        entities = template.get("issuer", {}).get("entities") or badge.get("issuer", {}).get("entities") or [{}]
        rows.append({"name": template["name"], "issuer": entities[0].get("entity", {}).get("name", ""),
                     "issued": badge.get("issued_at_date"), "expires": badge.get("expires_at_date"),
                     "url": f"https://www.credly.com/badges/{badge['id']}"})
    if not rows:
        raise ValueError("no badges")
    rows.sort(key=lambda row: (row["issued"] or "", row["name"]), reverse=True)
    (ROOT / "data/credly.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
    print(f"Credly: {len(rows)} badges")
    for row in rows:
        print(f"  {row['issued']} {row['expires']} {row['name']}")


for source in (github, credly):
    try:
        source()
    except (OSError, ValueError, KeyError) as error:
        print(f"Kept saved {source.__name__} data: {error}")
