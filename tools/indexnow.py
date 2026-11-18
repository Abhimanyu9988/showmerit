"""Tell Bing and the other IndexNow engines about every page in the sitemap, right after a deploy.

ChatGPT search draws on Bing's index, so a new article reaches it in hours instead of waiting for a crawl.
The key is public by design: build.py writes it to /<key>.txt and the engines check that file.
A failure here only prints a warning; it never fails the deploy.
"""
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build import INDEXNOW_KEY, SITE  # noqa: E402

HOST = SITE.removeprefix("https://")


def sitemap_urls():
    for attempt in range(6):                                   # the new deploy can take a minute to go live
        try:
            text = urllib.request.urlopen(f"{SITE}/sitemap.xml", timeout=20).read().decode()
            key = urllib.request.urlopen(f"{SITE}/{INDEXNOW_KEY}.txt", timeout=20).read().decode().strip()
            if key == INDEXNOW_KEY:
                return re.findall(r"<loc>([^<]+)</loc>", text)
        except (urllib.error.URLError, TimeoutError) as err:
            print(f"waiting for the live site: {err}")
        time.sleep(30)
    return []


def main():
    urls = sitemap_urls()
    if not urls:
        print("::warning::IndexNow skipped: the live key file or sitemap wasn't reachable")
        return
    body = json.dumps({"host": HOST, "key": INDEXNOW_KEY, "keyLocation": f"{SITE}/{INDEXNOW_KEY}.txt", "urlList": urls}).encode()
    request = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                                     headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(request, timeout=30) as reply:
            print(f"IndexNow accepted {len(urls)} URLs (HTTP {reply.status})")
    except urllib.error.HTTPError as err:
        print(f"::warning::IndexNow answered HTTP {err.code}: {err.read().decode()[:200]}")
    except (urllib.error.URLError, TimeoutError) as err:
        print(f"::warning::IndexNow unreachable: {err}")


if __name__ == "__main__":
    main()
