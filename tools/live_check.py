"""Check the live site from outside: HTTPS certificate, page answers, analytics tag, and the Pages setting."""
import json
import os
import socket
import ssl
import sys
import urllib.error
import urllib.request

HOST = "showmerit.com"
REPO = os.environ["GITHUB_REPOSITORY"]
problems = []


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "showmerit-live-check"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.status, response.url, response.read().decode("utf-8", "replace")


try:
    with socket.create_connection((HOST, 443), timeout=15) as raw:
        with ssl.create_default_context().wrap_socket(raw, server_hostname=HOST) as tls:
            cert = tls.getpeercert()
    print(f"Certificate OK: issuer {dict(x[0] for x in cert['issuer']).get('organizationName')}, names {[v for _, v in cert['subjectAltName']]}, until {cert['notAfter']}")
except OSError as error:
    problems.append(f"HTTPS certificate: {error}")

for url in (f"https://{HOST}/", f"https://{HOST}/abhimanyu/", f"https://www.{HOST}/", f"http://{HOST}/"):
    try:
        status, final, page = fetch(url)
        print(f"{url} -> {status} {final} analytics={'data-goatcounter' in page}")
        if url.startswith("https://showmerit") and "data-goatcounter" not in page:
            problems.append(f"{url}: no analytics tag")
    except (OSError, urllib.error.URLError) as error:
        problems.append(f"{url}: {error}")

request = urllib.request.Request(f"https://api.github.com/repos/{REPO}/pages", headers={
    "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json", "User-Agent": "showmerit"})
try:
    with urllib.request.urlopen(request, timeout=20) as response:
        pages = json.load(response)
    print("Pages:", {k: pages.get(k) for k in ("status", "cname", "https_enforced", "https_certificate")})
except OSError as error:
    print(f"Pages setting not readable: {error}")

for problem in problems:
    print(f"Problem: {problem}")
sys.exit(1 if problems else 0)
