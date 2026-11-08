"""Build the ShowMerit site from data/ and content/ into _site/. Links are root-absolute unless --preview is set."""
import datetime
import html
import json
import pathlib
import re
import shutil
import sys

import frontmatter
import markdown

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / ("_preview" if "--preview" in sys.argv else "_site")
PREVIEW = "--preview" in sys.argv
SITE = "https://showmerit.com"
GOATCOUNTER = "https://abhimanyu9988.goatcounter.com/count"
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
GROUPS = [("owner", "Code owner"), ("std", "Standards"), ("fix", "Fixes and docs")]
e = html.escape


def short(date):
    return f"{MONTHS[int(date[5:7]) - 1]} {int(date[8:])}"


def full(date):
    return f"{int(date[8:])} {MONTHS[int(date[5:7]) - 1]} {date[:4]}"


def plain_title(title):
    """Split a pull request title into its readable words and its component, keeping GitHub's wording."""
    scopes = []
    rest = title.strip()
    while True:
        tag = re.match(r"\[([^\]]+)\]\s*", rest)
        if not tag:
            break
        scopes.append(tag.group(1))
        rest = rest[tag.end():]
    prefix = re.match(r"(?:docs|fix|feat|chore)\(([^)]+)\):\s*|([a-z0-9-]+/[a-z0-9_-]+):\s*", rest)
    if prefix:
        scopes.append(prefix.group(1) or prefix.group(2))
        rest = rest[prefix.end():]
    scopes = [s for s in scopes if s != "chore"]
    return rest[:1].upper() + rest[1:], " / ".join(scopes)


def load_contributions(profile):
    rows = json.loads((ROOT / "data/contributions.json").read_text())
    shown = [r for r in rows if f"{r['repo']}#{r['number']}" not in profile["hide"]]
    for r in shown:
        r["project"] = profile["projects"].get(r["repo"], r["repo"].split("/")[1])
        r["plain"], r["scope"] = plain_title(r["title"])
        r["short_repo"] = r["repo"].split("/")[1].replace("opentelemetry-", "")
        if "code owner" in r["title"].lower():
            r["kind"] = "owner"
        elif r["repo"].endswith("/semantic-conventions"):
            r["kind"] = "std"
        else:
            r["kind"] = "fix"
    return shown


def loosen_lists(text):
    """Python-Markdown needs a blank line before a list, including inside a quote."""
    lines, fenced = [], False
    item = re.compile(r"^(> ?)?(\s*)([-*]|\d+\.) ")
    for line in text.split("\n"):
        if line.lstrip("> ").startswith("```"):
            fenced = not fenced
        previous = lines[-1] if lines else ""
        if not fenced and item.match(line) and previous.strip(" >") and not item.match(previous) and not previous.startswith("  "):
            lines.append(">" if line.startswith(">") else "")
        lines.append(line)
    return "\n".join(lines)


def load_articles(profile):
    articles = []
    for path in (ROOT / "content" / profile["slug"] / "articles").glob("*.md"):
        post = frontmatter.load(path)
        words = len(post.content.split())
        body = markdown.markdown(loosen_lists(post.content), extensions=["fenced_code", "tables", "sane_lists", "toc"])
        body = body.replace("<table>", '<div class="tablewrap"><table>').replace("</table>", "</table></div>")
        articles.append({**post.metadata, "slug": path.stem, "body": body, "minutes": max(1, round(words / 220)),
                         "date": str(post["date"]),
                         "url": f"/{profile['slug']}/articles/{path.stem}/",
                         "share": f"/{profile['slug']}/articles/{path.stem}/share.png"})
    return sorted(articles, key=lambda a: a["date"], reverse=True)


def load_badges():
    return json.loads((ROOT / "data/credly.json").read_text())


def clean(text):
    return re.sub(r"[\u2013\u2014]", "-", text).lower()


def holds(badge, code, title):
    """A badge counts if it is the named exam, and is still valid when the title needs active certifications."""
    name = clean(badge["name"])
    if title.get("active_only") and badge.get("expires") and badge["expires"] < datetime.date.today().isoformat():
        return False
    wanted = title.get("requires_names", {}).get(code)
    return wanted in name if wanted else name.startswith(code.lower() + ":") or name == code.lower()


def goal(title, badges):
    codes = title.get("requires") or list(title["requires_names"])
    steps = [{"code": c, "badge": next((b for b in badges if holds(b, c, title)), None)} for c in codes]
    done = sum(bool(s["badge"]) for s in steps)
    earned = any(clean(b["name"]) == title.get("earned_badge") for b in badges)
    return {**title, "steps": steps, "done": done, "total": len(steps), "earned": earned}


def load_goals(profile, badges):
    """Show a title when someone has started it or pinned it, until they earn it."""
    titles = json.loads((ROOT / "data/titles.json").read_text())
    goals = [goal(t, badges) for t in titles]
    shown = [g for g in goals if not g["earned"] and g["done"] < g["total"] and (g["done"] or g["id"] in profile["goals"])]
    return sorted(shown, key=lambda g: g["done"] / g["total"], reverse=True), [g for g in goals if g["earned"]]


def page(title, description, path, content, image="/share.png", kind="website", schema=None, author=None, published=None):
    canonical = SITE + path
    extra = (f'\n<meta name="author" content="{e(author)}">' if author else "") + \
            (f'<meta property="article:published_time" content="{e(published)}"><meta property="article:author" content="{e(author)}">' if published else "")
    file = ROOT / "static" / image.lstrip("/")
    if file.is_file():                    # LinkedIn keeps an image by its address, so a new picture needs a new address
        image += "?v=" + __import__("hashlib").sha1(file.read_bytes()).hexdigest()[:8]
    data = ""
    if schema:
        text = json.dumps(schema, ensure_ascii=False).replace("<", "\\u003c")
        data = f'<script type="application/ld+json">{text}</script>\n'
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{canonical}">
<link rel="alternate" type="application/rss+xml" title="ShowMerit articles" href="/feed.xml">
{data}<meta property="og:type" content="{kind}"><meta property="og:site_name" content="ShowMerit">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{canonical}"><meta property="og:image" content="{SITE}{image}">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">{extra}
<meta name="twitter:card" content="summary_large_image">
<script>if (location.protocol === "http:" && location.hostname.endsWith("showmerit.com")) location.replace("https://showmerit.com" + location.pathname + location.search + location.hash);</script>
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/style.css">
<script data-goatcounter="{GOATCOUNTER}" async src="https://gc.zgo.at/count.js"></script>
</head><body>
<header class="bar"><div class="wrap"><a class="brand" href="/">ShowMerit</a>
<nav><a href="/abhimanyu/">Profile</a><a href="/abhimanyu/articles/">Articles</a></nav></div></header>
{content}
<footer><div class="wrap"><span>ShowMerit. Every line links to its proof.</span><span>Free for now.</span></div></footer>
</body></html>
"""


def row(r):
    owner = " owner" if r["kind"] == "owner" else ""
    detail = f'{r["project"]} / {r["scope"]}' if r["scope"] else r["project"]
    return (f'<li><div class="claim">{e(r["plain"])}<small>{e(detail)}</small></div>'
            f'<a class="stub{owner}" href="{e(r["url"])}" aria-label="Proof: {e(r["short_repo"])} pull request {r["number"]}">'
            f'<span>{e(r["short_repo"])} #{r["number"]}</span><span>{short(r["date"])}</span></a></li>')


def article_row(a):
    return (f'<li><div class="claim"><a href="{a["url"]}">{e(a["title"])}</a></div>'
            f'<a class="stub" href="{a["url"]}" aria-label="Read: {e(a["title"])}">'
            f'<span>{short(a["date"])}</span><span>{a["minutes"]} min read</span></a></li>')


def chart(rows, today):
    recent = [r for r in rows if (today - datetime.date.fromisoformat(r["date"])).days <= 90]
    days = [datetime.date.fromisoformat(r["date"]) for r in recent]
    start, end = min(days) - datetime.timedelta(days=3), max(days) + datetime.timedelta(days=3)
    span = (end - start).days
    x = lambda d: round((d - start).days / span * 100, 2)
    ticks = [start + datetime.timedelta(days=round(span * i / 4)) for i in range(5)]
    axis = "".join(f'<span style="left:{x(t)}%">{short(t.isoformat())}</span>' for t in ticks)
    lanes = ""
    projects = sorted({r["project"] for r in recent}, key=lambda p: -sum(r["project"] == p for r in recent))
    for project in projects:
        marks, seen = "", {}
        for r in [r for r in recent if r["project"] == project]:
            n = seen[r["date"]] = seen.get(r["date"], 0) + 1
            left = x(datetime.date.fromisoformat(r["date"]))
            top = 50 + [0, -32, 32][n - 1]
            side = "r" if left > 55 else "l"
            owner = " owner" if r["kind"] == "owner" else ""
            label = f'{short(r["date"])}: {e(r["plain"])}'
            marks += (f'<a class="pr {side}{owner}" href="{e(r["url"])}" style="left:{left}%;top:{top}%" '
                      f'aria-label="{label}"><i></i><span>{label}</span></a>')
        total = sum(r["project"] == project for r in recent)
        lanes += (f'<div class="lane"><b>{e(project)}</b><div class="track">{marks}</div>'
                  f'<div class="count">{total} merged</div></div>')
    return f"""<section class="apm" aria-labelledby="apm-title"><div class="wrap">
<h2 id="apm-title">Merged work across projects</h2>
<p class="lead">Refreshed daily from GitHub. Each mark opens the pull request.</p>
<div class="axis"><span></span><div class="ticks">{axis}</div><span></span></div>
{lanes}
<div class="legend"><span><i></i>Merged pull request</span><span><i class="owner"></i>Became code owner</span></div>
</div></section>"""


def goals_section(goals):
    if not goals:
        return ""
    cards = ""
    for g in goals:
        stamps = ""
        for s in g["steps"]:
            if s["badge"]:
                stamps += f'<a class="stamp done" href="{e(s["badge"]["url"])}" aria-label="{e(s["code"])}: passed, open proof">{e(s["code"])}</a>'
            else:
                stamps += f'<span class="stamp" aria-label="{e(s["code"])}: to go">{e(s["code"])}</span>'
        left = g["total"] - g["done"]
        names = ", ".join(s["code"] for s in g["steps"] if not s["badge"])
        word = "certification" if left == 1 else "certifications"
        note = f'<p class="note">{e(g["note"])}</p>' if g.get("note") else ""
        cards += (f'<div class="goal"><h3>{e(g["title"])}</h3><p><b>{g["done"]} of {g["total"]} done.</b> '
                  f'{left} {word} to go: {e(names)}.</p><div class="stamps">{stamps}</div>{note}'
                  f'<p class="note"><a href="{e(g["source"])}">Requirements</a></p></div>')
    return f'<section class="group wrap"><h2>Goals ({len(goals)})</h2>{cards}</section>'


def current(badge, today):
    return not badge.get("expires") or badge["expires"] >= today


def cert_row(b, earned, count=True):
    title = b["name"]
    issued = short(b["issued"]) + " " + b["issued"][:4] if b.get("issued") else "Credly"
    highlight = " owner" if title in earned else ""
    mark = " data-cert" if count else ""
    return (f'<li{mark}><div class="claim">{e(title)}<small>{e(b.get("issuer") or "Credly")}</small></div>'
            f'<a class="stub{highlight}" href="{e(b["url"])}" aria-label="Proof on Credly: {e(title)}">'
            f'<span>Credly</span><span>{issued}</span></a></li>')


def certs_section(badges, earned_titles, today):
    if not badges:
        return ""
    earned = {g["title"] for g in earned_titles}
    now = today.isoformat()
    active = sorted([b for b in badges if current(b, now)], key=lambda b: b["name"] not in earned)
    earlier = [b for b in badges if not current(b, now)]
    more = ""
    if earlier:
        more = (f'<details><summary>{len(earlier)} earlier credentials</summary><ul class="ledger" style="margin-top:10px">'
                f'{"".join(cert_row(b, earned, False) for b in earlier)}</ul></details>')
    return (f'<section class="group wrap"><h2>Credentials ({len(active)})</h2>'
            f'<ul class="ledger">{"".join(cert_row(b, earned) for b in active)}</ul>{more}</section>')


def facts(rows, articles, badges):
    items = [(len(rows), "merged pull requests"), (len({r["repo"] for r in rows}), "projects"),
             (sum(r["kind"] == "owner" for r in rows), "code owner roles")]
    active = sum(current(b, datetime.date.today().isoformat()) for b in badges)
    if active:
        items.append((active, "current credentials"))
    items.append((len(articles), "articles"))
    return '<dl class="facts">' + "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for v, k in items) + "</dl>"


def person(profile):
    return {"@context": "https://schema.org", "@type": "Person", "name": profile["name"], "description": profile["lede"],
            "url": f"{SITE}/{profile['slug']}/", "sameAs": [link["url"] for link in profile["links"]]}


def llms(profile, articles):
    lines = ["# ShowMerit", "", "> Professional profiles where every claim links to its proof.", "",
             f"## {profile['name']}", "", profile["lede"], "", f"- [Profile]({SITE}/{profile['slug']}/)", "", "## Articles", ""]
    lines += [f"- [{a['title']}]({SITE}{a['url']}article.md): {a['description']}" for a in articles]
    return "\n".join(lines) + "\n"


def feed(profile, articles):
    items = "".join(
        f"<item><title>{e(a['title'])}</title><link>{SITE}{a['url']}</link><guid>{SITE}{a['url']}</guid>"
        f"<pubDate>{datetime.date.fromisoformat(a['date']).strftime('%a, %d %b %Y')} 12:00:00 GMT</pubDate>"
        f"<description>{e(a['description'])}</description></item>" for a in articles)
    return ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>ShowMerit articles</title>'
            f"<link>{SITE}/{profile['slug']}/articles/</link><description>Articles by {e(profile['name'])}</description>"
            f"{items}</channel></rss>\n")


def home(profile, rows, articles):
    picks = [r for r in rows if r["kind"] == "owner"][:2]
    picks += [r for r in rows if r["kind"] == "std"][:1] + [r for r in rows if r["kind"] == "fix"][:1]
    content = f"""<main>
<section class="hero"><div class="wrap">
<h1>A profile where every claim links to its <span class="mark">proof</span>.</h1>
<p>Type your GitHub username and see your merged work, with proof, in seconds. Free for now.</p>
<form id="try-form" class="try" autocomplete="off"><label for="try-user">GitHub username</label>
<div><input id="try-user" name="user" type="text" inputmode="text" autocapitalize="none" spellcheck="false" maxlength="39" placeholder="your-username" required>
<button class="button" type="submit">See my proof</button></div></form>
<p class="note">No sign-up. Nothing is saved. Or <a href="/{profile['slug']}/">see a real profile</a>.</p>
<div id="try-result" aria-live="polite"></div>
</div></section>
<section class="block wrap">
<h2>From the founder's profile</h2>
<p class="lead">{e(profile['name'])}'s recent work. Each item opens the record on GitHub.</p>
<ul class="ledger">{''.join(row(r) for r in picks)}</ul>
</section>
<section class="block wrap">
<h2>How it works</h2>
<ol class="steps">
<li><b>Start with GitHub</b>Your username is enough to see your merged work.</li>
<li><b>Your profile builds itself</b>Your merged work is grouped by project, with no document to maintain.</li>
<li><b>Every line keeps its proof</b>Readers can open the source behind any claim.</li>
</ol>
</section>
<section class="block wrap">
<h2>Latest articles</h2>
<ul class="ledger" style="margin-top:16px">{''.join(article_row(a) for a in articles[:3])}</ul>
</section>
<section class="closing"><div class="wrap"><h2>See how a profile reads.</h2><a class="button" href="/{profile['slug']}/">See a real profile</a></div></section>
</main>
<script src="/try.js" defer></script>"""
    return page("ShowMerit: a profile where every claim links to its proof",
                "Add your public links and ShowMerit builds your professional profile, with proof behind every line.",
                "/", content)


def profile_page(profile, rows, articles, today, badges, goals, earned):
    groups = ""
    for kind, name in GROUPS:
        items = [r for r in rows if r["kind"] == kind]
        if items:
            groups += (f'<section class="group wrap"><h2>{name} ({len(items)})</h2>'
                       f'<ul class="ledger">{"".join(row(r) for r in items)}</ul></section>')
    links = "".join(f'<a href="{e(l["url"])}">{e(l["label"])}</a>' for l in profile["links"])
    content = f"""<main>
<section class="person wrap"><h1>{e(profile['name'])}</h1><p>{e(profile['lede'])}</p>
<div class="links">{links}</div>{facts(rows, articles, badges)}</section>
{chart(rows, today)}
{goals_section(goals)}
{groups}
{certs_section(badges, earned, today)}
<section class="group wrap"><h2>Articles ({len(articles)})</h2>
<ul class="ledger">{''.join(article_row(a) for a in articles)}</ul></section>
</main>"""
    return page(f"{profile['name']} on ShowMerit", profile["lede"], f"/{profile['slug']}/", content, author=profile["name"],
                image=f"/{profile['slug']}/share.png", kind="profile", schema=person(profile))


def articles_page(profile, articles):
    content = f"""<main><section class="person wrap"><h1>Articles</h1>
<p>By <a href="/{profile['slug']}/">{e(profile['name'])}</a>. Lab-tested guides and open source notes.</p></section>
<section class="wrap"><ul class="ledger">{''.join(article_row(a) for a in articles)}</ul></section></main>"""
    return page(f"Articles by {profile['name']}", f"Articles by {profile['name']} on ShowMerit.",
                f"/{profile['slug']}/articles/", content, image=f"/{profile['slug']}/share.png")


def run_box(article):
    if not article.get("lab_url"):
        return ""
    path = article["lab_url"].split("/tree/main/")[1]
    clone = f"git clone https://github.com/Abhimanyu9988/showmerit.git\ncd showmerit/{path}"
    options = ""
    if (ROOT / path / "check.sh").is_file():
        options += (f'<div><h3>On your laptop</h3><p>Runs the app with and without the agent on your own machine and counts what the agent reports. Free, needs Docker, jq and Python 3, and took about 2 minutes in our test. '
                    f'It uses no AWS or Splunk.</p><pre><code>{e(clone)}\nbash check.sh</code></pre></div>')
    build = next((m for m in re.findall(r'<h2 id="([^"]+)">', article["body"]) if m.startswith(("build", "how-to-build", "run-it", "reproduce"))), "")
    jump = f'<a href="#{build}">Follow the steps below</a>' if build else "Follow the steps in this article"
    options += (f'<div><h3>On your AWS account</h3><p>The full lab with your own AWS account and Splunk token. {jump}, '
                'then run its clean up step so nothing keeps running.</p>'
                f'<pre><code>{e(clone)}</code></pre></div>')
    return f'<section class="run wrap" aria-labelledby="run-title"><h2 id="run-title">Run this yourself</h2><div class="options">{options}</div></section>'


def article_page(profile, article, others):
    ticket = [f'<b><a href="/{profile["slug"]}/">{e(profile["name"])}</a></b>', f'<span>Published {full(article["date"])}</span>',
              f'<span>{article["minutes"]} min read</span>']
    if article.get("region"):
        ticket.append(f'<span>Tested in {e(article["region"])}</span>')
    if article.get("lab_url"):
        ticket.append(f'<a href="{e(article["lab_url"])}">Lab code</a>')
    if article.get("evidence_url"):
        ticket.append(f'<a href="{e(article["evidence_url"])}">Lab evidence</a>')
    content = f"""<main><section class="head"><div class="wrap">
<div><h1>{e(article['title'])}</h1><p class="desc">{e(article['description'])}</p></div>
<div class="ticket">{''.join(ticket)}</div></div></section>
{run_box(article)}
<article class="prose wrap">{article['body']}</article>
<section class="next wrap"><h2>Read next</h2><ul class="ledger">{article_row(others[0])}</ul>
<p class="more">{e(profile['lede'])} <a href="/{profile['slug']}/">See the proof</a></p></section></main>"""
    schema = {"@context": "https://schema.org", "@type": "TechArticle", "headline": article["title"],
              "description": article["description"], "datePublished": article["date"], "image": SITE + article["share"],
              "url": SITE + article["url"], "mainEntityOfPage": SITE + article["url"], "author": person(profile),
              "keywords": ", ".join(article.get("tags", []))}
    return page(article["title"], article["description"], article["url"], content, image=article["share"], kind="article", schema=schema,
                author=profile["name"], published=article["date"])


def write(path, text):
    target = OUT / path.lstrip("/") / "index.html" if path.endswith("/") else OUT / path.lstrip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def relative(text, depth):
    """For a preview in a sub-folder: turn root-absolute links into relative ones that name index.html."""
    up = "../" * depth

    def fix(match):
        attr, url = match.group(1), match.group(2)
        if url.endswith("/"):
            url += "index.html"
        return f'{attr}="{up}{url.lstrip("/")}"'

    return re.sub(r'\b(href|src)="(/(?!/)[^"]*)"', fix, text)


def main():
    profile = json.loads((ROOT / "data/profile.json").read_text())
    today = datetime.date.today()
    rows = load_contributions(profile)
    articles = load_articles(profile)
    shutil.rmtree(OUT, ignore_errors=True)
    shutil.copytree(ROOT / "static", OUT)
    slug = profile["slug"]
    write("/", home(profile, rows, articles))
    badges = load_badges()
    goals, earned = load_goals(profile, badges)
    print(f"Goals: {[(g['title'], g['done'], g['total']) for g in goals]}. Earned: {[g['title'] for g in earned]}")
    write(f"/{slug}/", profile_page(profile, rows, articles, today, badges, goals, earned))
    write(f"/{slug}/articles/", articles_page(profile, articles))
    for i, article in enumerate(articles):
        write(article["url"], article_page(profile, article, articles[(i + 1) % len(articles):] + articles))
        source = frontmatter.load(ROOT / "content" / slug / "articles" / f"{article['slug']}.md")
        write(article["url"] + "article.md", f"# {article['title']}\n\n{article['description']}\n\nBy {profile['name']}. "
              f"Published {article['date']}. Page: {SITE}{article['url']}\n\n{source.content}")
    write("/404.html", page("Page not found", "This page isn't on ShowMerit.", "/404.html",
                            '<main><section class="person wrap"><h1>Not here</h1><p>This page isn\'t on ShowMerit. '
                            f'<a href="/{slug}/">See a real profile</a>.</p></section></main>'))
    write("/llms.txt", llms(profile, articles))
    write("/feed.xml", feed(profile, articles))
    urls = [("/", today.isoformat()), (f"/{slug}/", today.isoformat()), (f"/{slug}/articles/", articles[0]["date"])]
    urls += [(a["url"], a["date"]) for a in articles]
    sitemap = "".join(f"<url><loc>{SITE}{u}</loc><lastmod>{d}</lastmod></url>" for u, d in urls)
    write("/sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sitemap}</urlset>\n')
    write("/robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    if PREVIEW:
        for file in OUT.rglob("*.html"):
            depth = len(file.relative_to(OUT).parts) - 1
            text = re.sub(r'<script data-goatcounter.*?</script>\n', "", file.read_text())
            file.write_text(relative(text, depth))


if __name__ == "__main__":
    main()
