"""Run: python tests/test_dns_setup.py"""
import json
import os
import pathlib
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
RECORDS = []
SEEN = []


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or "{}")
        SEEN.append(self.path)
        assert self.headers["X-API-Key"] == "k" and "apikey" not in body
        reply = {"status": "SUCCESS"}
        if "/retrieve/" in self.path:
            reply["records"] = RECORDS
        elif "/delete/" in self.path:
            RECORDS[:] = [r for r in RECORDS if r["id"] != self.path.rsplit("/", 1)[1]]
        elif "/create/" in self.path:
            name = f'{body["name"]}.showmerit.com' if body["name"] else "showmerit.com"
            RECORDS.append({"id": str(100 + len(SEEN)), "name": name, "type": body["type"], "content": body["content"]})
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(data)


def run(*args):
    env = {**os.environ, "PORKBUN_BASE": f"http://127.0.0.1:{server.server_port}", "PORKBUN_API_KEY": "k", "PORKBUN_SECRET_KEY": "s"}
    done = subprocess.run([sys.executable, "tools/dns_setup.py", *args], cwd=ROOT, env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout


server = HTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=server.serve_forever, daemon=True).start()
RECORDS[:] = [{"id": "1", "name": "showmerit.com", "type": "ALIAS", "content": "pixie.porkbun.com"},
              {"id": "2", "name": "*.showmerit.com", "type": "CNAME", "content": "pixie.porkbun.com"},
              {"id": "3", "name": "showmerit.com", "type": "MX", "content": "mail.example.com"},
              {"id": "4", "name": "showmerit.com", "type": "TXT", "content": "v=spf1 -all"},
              {"id": "5", "name": "showmerit.com", "type": "A", "content": "185.199.108.153"}]
before = list(RECORDS)
output = run()
assert "Dry run" in output and RECORDS == before and not any("create" in p or "delete" in p for p in SEEN), output
output = run("--apply")
assert "All five records" in output, output
kinds = sorted((r["name"], r["type"], r["content"]) for r in RECORDS)
assert ("showmerit.com", "MX", "mail.example.com") in kinds and ("showmerit.com", "TXT", "v=spf1 -all") in kinds
assert not any(r["content"] == "pixie.porkbun.com" for r in RECORDS)
assert sum(r["type"] == "A" for r in RECORDS) == 4 and ("www.showmerit.com", "CNAME", "abhimanyu9988.github.io") in kinds
assert "already correct" in run("--apply")
print("DNS tests pass")
