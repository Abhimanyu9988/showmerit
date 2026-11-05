"""Open a "Ready to post" issue for each new article, so GitHub emails Abhi the LinkedIn text."""
import json
import os
import pathlib
import urllib.parse
import urllib.request

import frontmatter

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO = os.environ["GITHUB_REPOSITORY"]
OWNER = REPO.split("/")[0]
HEADERS = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json",
           "User-Agent": "showmerit"}


def api(path, body=None):
    data = json.dumps(body).encode() if body else None
    request = urllib.request.Request(f"https://api.github.com/repos/{REPO}/{path}", data=data, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def body(post, url, image):
    text = post["linkedin"].strip()
    compose = "https://www.linkedin.com/feed/?shareActive=true&text=" + urllib.parse.quote(text)
    return "\n".join([
        f"**Article:** {url}", "", f"**[Open this post in LinkedIn]({compose})** with the text filled in, then tap Post.", "",
        "**Or copy this text:**", "", "```text", text, "```", "", "**Picture:**", "", f"![LinkedIn picture]({image})"])


titles = {issue["title"] for issue in api("issues?state=all&per_page=100")}
for path in sorted((ROOT / "content").glob("*/articles/*.md")):
    post = frontmatter.load(path)
    title = f"Ready to post: {post['title']}"
    if not post.get("linkedin") or title in titles:
        continue
    slug = path.parent.parent.name
    url = f"https://showmerit.com/{slug}/articles/{path.stem}/"
    issue = api("issues", {"title": title, "body": body(post, url, url + "share.png"), "assignees": [OWNER]})
    print(f"Opened {issue['html_url']}")
