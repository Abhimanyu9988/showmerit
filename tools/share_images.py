"""Make the 1200x630 LinkedIn images into static/. Run locally when an article is added: python tools/share_images.py"""
import asyncio
import html
import json
import pathlib

import frontmatter
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
FONTS = (ROOT / "static/fonts").as_uri()


def card(title, name, line, date, address):
    size = 128 if len(title) < 34 else 108 if len(title) < 52 else 90 if len(title) < 72 else 78
    rows = "".join(f"<div>{html.escape(t)}</div>" for t in (line, date) if t)
    return f"""<!doctype html><meta charset="utf-8"><style>
@font-face {{ font-family: D; src: url({FONTS}/big-shoulders-display-latin-800-normal.woff2); font-weight: 800; }}
@font-face {{ font-family: M; src: url({FONTS}/ibm-plex-mono-latin-500-normal.woff2); }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; width: 1200px; height: 630px; background: #1a3fd0; color: #fff; display: grid; grid-template-columns: 1fr 340px; }}
.left {{ padding: 54px 44px 44px 60px; display: flex; flex-direction: column; justify-content: space-between; min-width: 0; }}
h1 {{ font: 800 {size}px/1 D; margin: 0; text-wrap: balance; }}
.brand {{ font: 800 40px/1 D; }}
.stub {{ background: #e6f05a; color: #0b1b3f; border-left: 8px dotted #1a3fd0; padding: 54px 34px 44px; display: flex; flex-direction: column; justify-content: space-between; font: 500 25px/1.3 M; }}
.stub b {{ font: 800 58px/1 D; display: block; margin-bottom: 18px; }}
.stub div {{ margin-bottom: 8px; }}
.addr {{ font-size: 18px; white-space: nowrap; }}
</style><div class="left"><h1>{html.escape(title)}</h1><div class="brand">ShowMerit</div></div>
<div class="stub"><div><b>{html.escape(name)}</b>{rows}</div><div class="addr">{html.escape(address)}</div></div>"""


async def main():
    profile = json.loads((ROOT / "data/profile.json").read_text())
    slug, name, line = profile["slug"], profile["name"], profile["share_line"]
    jobs = [(ROOT / "static/share.png", card("A profile where every claim links to its proof.", "ShowMerit", "", "", "showmerit.com")),
            (ROOT / f"static/{slug}/share.png", card("Every line links to its proof.", name, line, "", f"showmerit.com/{slug}"))]
    for path in (ROOT / f"content/{slug}/articles").glob("*.md"):
        post = frontmatter.load(path)
        date = str(post["date"])
        when = f"{MONTHS[int(date[5:7]) - 1]} {int(date[8:])}, {date[:4]}"
        jobs.append((ROOT / f"static/{slug}/articles/{path.stem}/share.png", card(post["title"], name, line, when, f"showmerit.com/{slug}")))
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1200, "height": 630})
        scratch = ROOT / ".share.html"
        for target, markup in jobs:
            target.parent.mkdir(parents=True, exist_ok=True)
            scratch.write_text(markup)
            await page.goto(scratch.as_uri())
            await page.evaluate("document.fonts.ready")
            await page.screenshot(path=str(target))
        scratch.unlink()
        await browser.close()
    print(f"Made {len(jobs)} images")


asyncio.run(main())
