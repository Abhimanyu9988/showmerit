"""Run: python tests/test_rechecks.py. The recheck line on each article, and the cleaning of the results it reads."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import build
import rechecks

RUN = "https://github.com/Abhimanyu9988/Abhimanyu9988.github.io/actions/runs/42"
OLD = {"agent": "2.33.1", "splunk-otel-collector chart": "0.163.1", "postgres": "16.4-alpine"}
NEW = {"agent": "2.34.0", "splunk-otel-collector chart": "0.163.1", "postgres": "16.10-alpine"}


def free(*results, day="2026-11-16", **extra):
    return {"free": {"date": day, "run": RUN, "results": [{"set": s, "versions": v, "passed": p} for s, v, p in results], **extra}}


line = build.recheck_line(free(("article", OLD, True), ("newest", NEW, True)))
assert line == ("Rechecked 16 Nov 2026: works with agent 2.33.1 and 2.34.0, splunk-otel-collector chart 0.163.1 (on a GitHub runner)",
                RUN, False), line
line = build.recheck_line(free(("article", OLD, True), newest_is_article=True))
assert line[0] == "Rechecked 16 Nov 2026: works with agent 2.33.1, splunk-otel-collector chart 0.163.1, still the newest (on a GitHub runner)", line
line = build.recheck_line(free(("article", OLD, True), ("newest", NEW, False)))
assert line == ("Recheck on 16 Nov 2026: works with agent 2.33.1, splunk-otel-collector chart 0.163.1; failed with agent 2.34.0, "
                "splunk-otel-collector chart 0.163.1, investigating (on a GitHub runner)", RUN, True), line
line = build.recheck_line(free(("article", OLD, False), ("newest", NEW, False)))
assert line[0] == "Recheck on 16 Nov 2026 failed with agent 2.33.1 and 2.34.0, splunk-otel-collector chart 0.163.1, investigating (on a GitHub runner)", line
assert line[2] is True

aws = {"aws": {"date": "2026-11-20", "run": RUN, "versions": {"keda chart": "2.22.0", "python": "3.14-slim"}, "passed": True}}
assert build.recheck_line(aws)[0] == "Rechecked 20 Nov 2026: works with keda chart 2.22.0 (on AWS)"
failed_aws = {"aws": {**aws["aws"], "passed": False}}
assert build.recheck_line(failed_aws)[0] == "Recheck on 20 Nov 2026 failed with keda chart 2.22.0, investigating (on AWS)"
images_only = {"aws": {**aws["aws"], "versions": {"busybox": "1.37.0"}}}
assert build.recheck_line(images_only)[0] == "Rechecked 20 Nov 2026: works with busybox 1.37.0 (on AWS)"
nothing = {"aws": {**aws["aws"], "versions": {}}}
assert build.recheck_line(nothing)[0] == "Rechecked 20 Nov 2026: works with the lab as published (on AWS)"

both = {**free(("article", OLD, False), day="2026-12-01"), **aws}
assert "GitHub runner" in build.recheck_line(both)[0], "the newer recheck is shown"
assert "on AWS" in build.recheck_line({**free(("article", OLD, True)), **aws})[0]
assert build.recheck_line({**free(), **aws})[0].endswith("(on AWS)"), "a link-only free run is not a lab recheck"
assert build.recheck_line({}) is None and build.recheck_html(None) == ""
html = build.recheck_html(free(("article", {"agent": "<b>2</b>"}, False)))
assert '<p class="recheck failed"><a href="' + RUN + '">' in html and "<b>" not in html, html

# Cleaning: only expected fields, versions as plain words, and runs of the pipeline repo
good = {"articles": {"java-agent": {**free(("article", OLD, True), ("newest", NEW, False), newest_is_article=False,
                                           links={"checked": 3, "broken": 1}), **aws},
                     "Bad Slug": free(("article", OLD, True))}}
got = rechecks.clean(good)
assert list(got["articles"]) == ["java-agent"], got
assert "links" not in got["articles"]["java-agent"]["free"], "only what the page shows is kept"
assert got["articles"]["java-agent"]["aws"]["passed"] is True
bad_run = {"articles": {"a": {"free": {"date": "2026-11-16", "run": "https://evil.example/run", "results": []}}}}
assert rechecks.clean(bad_run) == {"articles": {}}
bad_version = {"articles": {"a": free(("article", {"agent": "2.3<script>"}, True))}}
assert rechecks.clean(bad_version) == {"articles": {}}
bad_passed = {"articles": {"a": free(("article", OLD, "yes"))}}
assert rechecks.clean(bad_passed) == {"articles": {}}
assert rechecks.clean(None) == {"articles": {}} and rechecks.clean({"articles": []}) == {"articles": {}}

# The build check refuses a recheck line that has no run link
site = ROOT / "_site"
if (site / "abhimanyu/index.html").is_file():
    page = next((site / "abhimanyu/articles").glob("*/index.html"))
    keep = page.read_text()
    try:
        page.write_text(keep.replace('<p class="desc">', '<p class="recheck">Rechecked 1 Jan 2026: works</p><p class="desc">', 1))
        done = subprocess.run([sys.executable, "tools/check.py"], cwd=ROOT, capture_output=True, text=True)
        assert done.returncode == 1 and "recheck line without its run link" in done.stdout, done.stdout
    finally:
        page.write_text(keep)
print("recheck tests pass")
