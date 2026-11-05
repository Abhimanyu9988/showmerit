"""Fail the build if a page has a broken internal link, a missing share image, or counts that don't reconcile."""
import pathlib
import re
import struct
import sys

SITE = pathlib.Path(__file__).resolve().parent.parent / (sys.argv[1] if len(sys.argv) > 1 else "_site")
problems = []


def exists(page, url):
    url = url.split("#")[0].split("?")[0]
    if not url:
        return True
    target = SITE / url.lstrip("/") if url.startswith("/") else (page.parent / url).resolve()
    return target.is_file() or (target / "index.html").is_file()


pages = list(SITE.rglob("*.html"))
if len(pages) < 5:
    problems.append(f"only {len(pages)} pages built")
for page in pages:
    text = page.read_text()
    name = page.relative_to(SITE)
    if "<title>" not in text:
        problems.append(f"{name}: no title")
    for url in re.findall(r'\b(?:href|src)="([^"]+)"', text):
        if not re.match(r"[a-z]+:|//", url) and not exists(page, url):
            problems.append(f"{name}: broken link {url}")
    for url in re.findall(r'abhimanyu9988\.github\.io/[^"\s<)]*', text):
        problems.append(f"{name}: old site link {url}")
    image = re.search(r'og:image" content="https://showmerit\.com([^"]+)"', text)
    if image:
        file = SITE / image.group(1).lstrip("/")
        if not file.is_file():
            problems.append(f"{name}: no share image {image.group(1)}")
        elif struct.unpack(">II", file.read_bytes()[16:24]) != (1200, 630):
            problems.append(f"{name}: share image isn't 1200x630")

profile = SITE / "abhimanyu/index.html"
if profile.is_file():
    text = profile.read_text()
    facts = dict((k, int(v)) for k, v in re.findall(r"<dt>([^<]+)</dt><dd>(\d+)</dd>", text))
    groups = [int(n) for n in re.findall(r"<h2>(?:Code owner|Standards|Fixes and docs) \((\d+)\)</h2>", text)]
    if sum(groups) != facts.get("merged pull requests"):
        problems.append(f"profile: groups {groups} don't add up to {facts.get('merged pull requests')}")
    if facts.get("current credentials", 0) != text.count("data-cert"):
        problems.append("profile: credentials count doesn't match the list")
    if text.count('class="pr ') > facts.get("merged pull requests", 0):
        problems.append("profile: chart shows more marks than the count")

for problem in problems:
    print(problem)
print(f"{len(pages)} pages checked, {len(problems)} problems")
sys.exit(1 if problems else 0)
