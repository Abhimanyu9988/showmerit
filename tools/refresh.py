"""Refresh merged pull requests from GitHub. On any failure, the saved data stays as it was."""
import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
user = json.loads((ROOT / "data/profile.json").read_text())["github"]
query = urllib.parse.quote(f"author:{user} is:pr is:merged -user:{user}")
request = urllib.request.Request(
    f"https://api.github.com/search/issues?q={query}&per_page=100&sort=updated",
    headers={"Accept": "application/vnd.github+json", "User-Agent": "showmerit",
             "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"})
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        found = json.load(response)
except OSError as error:
    sys.exit(f"Kept saved data: {error}")
if found.get("incomplete_results") or not found.get("items"):
    sys.exit("Kept saved data: incomplete result")
rows = [{"date": item["closed_at"][:10], "repo": item["repository_url"].split("/repos/")[1],
         "number": item["number"], "title": item["title"], "url": item["html_url"]}
        for item in found["items"]]
rows.sort(key=lambda row: (row["date"], row["number"]), reverse=True)
(ROOT / "data/contributions.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
print(f"Saved {len(rows)} merged pull requests")
