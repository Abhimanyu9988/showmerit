# ShowMerit

A professional profile where every claim links to its proof. Live at showmerit.com.

- `data/` holds the profile and merged pull requests.
- `content/` holds articles.
- `static/` holds styles, fonts and images.
- `build.py` builds the site, and `tools/check.py` stops a broken build from going live.
- `tools/refresh.py` updates pull requests from GitHub each day.
- `data/rechecks.json` holds each lab's latest recheck, copied each day from the pipeline repo's analytics branch by `tools/rechecks.py`. Each article shows it, linked to the run.
- `tools/share_images.py` makes the LinkedIn images when an article is added.

Fonts are Big Shoulders Display, Libre Franklin and IBM Plex Mono, under the SIL Open Font License.

To build locally: `pip install -r requirements.txt && python build.py && python tools/check.py`
