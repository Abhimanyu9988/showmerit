"""Re-save the custom domain so GitHub requests the HTTPS certificate, and turn on HTTPS when it's ready."""
import json
import os
import sys
import urllib.error
import urllib.request

REPO = os.environ["GITHUB_REPOSITORY"]


def call(method, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(f"https://api.github.com/repos/{REPO}/pages", data=data, method=method, headers={
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json", "User-Agent": "showmerit"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode()
            print(method, response.status)
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as error:
        print(method, error.code, error.read().decode()[:200])
        return None


if sys.argv[1:] == ["resave"]:
    if call("PUT", {"cname": None}) is None:
        sys.exit(1)
    if call("PUT", {"cname": "showmerit.com"}) is None:
        sys.exit("Domain was cleared and could not be saved again")
else:
    call("PUT", {"https_enforced": True})
print({k: v for k, v in (call("GET") or {}).items() if k in ("cname", "https_enforced", "https_certificate", "status")})
