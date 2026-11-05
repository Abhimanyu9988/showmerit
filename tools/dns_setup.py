"""Point showmerit.com at GitHub Pages through Porkbun. Reports the changes, and writes them only with --apply.

It changes address records on the root, www and * only, so mail and verification records stay as they are.
"""
import json
import os
import sys
import urllib.error
import urllib.request

DOMAIN = "showmerit.com"
BASE = os.environ.get("PORKBUN_BASE", "https://api.porkbun.com/api/json/v3")
WANTED = [("", "A", "185.199.108.153"), ("", "A", "185.199.109.153"), ("", "A", "185.199.110.153"),
          ("", "A", "185.199.111.153"), ("www", "CNAME", "abhimanyu9988.github.io")]
ADDRESS_TYPES = {"A", "AAAA", "ALIAS", "CNAME"}


def call(path, body=None):
    request = urllib.request.Request(f"{BASE}/{path}", data=json.dumps(body or {}).encode(), method="POST", headers={
        "Content-Type": "application/json", "User-Agent": "showmerit-dns",
        "X-API-Key": os.environ["PORKBUN_API_KEY"], "X-Secret-API-Key": os.environ["PORKBUN_SECRET_KEY"]})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        result = json.load(error)
    if result.get("status") != "SUCCESS":
        sys.exit(f"Porkbun refused {path.split('/')[1]}: {result.get('code', '')} {result.get('message', '')}. Nothing further was changed.")
    for warning in result.get("warnings") or []:
        print(f"Warning: {warning}")
    return result


def short_name(record):
    name = record.get("name", "")
    return "" if name == DOMAIN else name.removesuffix(f".{DOMAIN}")


def plan(records):
    """Return address records to delete and wanted records to create."""
    current = [r for r in records if r.get("type") in ADDRESS_TYPES and short_name(r) in {"", "www", "*"}]
    keep = {(short_name(r), r["type"], r["content"].rstrip(".").lower()) for r in current}
    remove = [r for r in current if (short_name(r), r["type"], r["content"].rstrip(".").lower()) not in WANTED]
    return remove, [w for w in WANTED if w not in keep]


def show(record):
    return f"{record[1]} {record[0] or '@'} -> {record[2]}"


def main():
    apply = "--apply" in sys.argv
    remove, add = plan(call(f"dns/retrieve/{DOMAIN}")["records"])
    for record in remove:
        print(f"Delete: {show((short_name(record), record['type'], record['content']))}")
    for record in add:
        print(f"Add: {show(record)}")
    if not remove and not add:
        print("All records are already correct.")
        return
    if not apply:
        print("Dry run. Nothing was changed.")
        return
    for record in remove:
        call(f"dns/delete/{DOMAIN}/{record['id']}")
    for name, kind, content in add:
        call(f"dns/create/{DOMAIN}", {"name": name, "type": kind, "content": content, "ttl": "600"})
    left, missing = plan(call(f"dns/retrieve/{DOMAIN}")["records"])
    if left or missing:
        sys.exit(f"Records don't match after the change: {len(left)} extra, {len(missing)} missing.")
    print("Done. All five records are in place.")


if __name__ == "__main__":
    main()
