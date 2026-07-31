from __future__ import annotations

import json
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .io_utils import write_jsonl

BASE = "https://rest.uniprot.org/uniprotkb/search"


def _ssl_context() -> ssl.SSLContext:
    """Use a verified system CA bundle when framework Python misses macOS Keychain CAs."""
    for candidate in (ssl.get_default_verify_paths().cafile, "/etc/ssl/cert.pem"):
        if candidate and Path(candidate).is_file():
            return ssl.create_default_context(cafile=candidate)
    return ssl.create_default_context()


def _next_link(header: str | None) -> str | None:
    if not header:
        return None
    for part in header.split(","):
        bits = part.split(";")
        if len(bits) > 1 and 'rel="next"' in bits[1]:
            return bits[0].strip()[1:-1]
    return None


def fetch_reviewed_since(start_date: str, out_path: Path, limit: int | None, page_size: int = 100) -> dict:
    query = f"reviewed:true AND date_created:[{start_date} TO *]"
    params = urllib.parse.urlencode({"query": query, "format": "json", "size": min(page_size, 500)})
    url: str | None = f"{BASE}?{params}"
    rows: list[dict] = []
    pages: list[dict] = []
    while url and (limit is None or len(rows) < limit):
        request = urllib.request.Request(url, headers={"User-Agent": "ProteinArena-Repro-2026/0.1"})
        with urllib.request.urlopen(request, timeout=90, context=_ssl_context()) as response:
            payload = json.load(response)
            pages.append({
                "uniprot_release": response.headers.get("x-uniprot-release"),
                "uniprot_release_date": response.headers.get("x-uniprot-release-date"),
                "total_results": response.headers.get("x-total-results"),
            })
            batch = payload.get("results", [])
            if limit is not None:
                batch = batch[: max(0, limit - len(rows))]
            rows.extend(batch)
            url = _next_link(response.headers.get("Link"))
        if url:
            time.sleep(0.15)
    count = write_jsonl(out_path, rows)
    metadata = {"endpoint": BASE, "query": query, "downloaded": count, "pages": pages}
    meta_path = out_path.with_suffix(out_path.suffix + ".meta.json")
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return {"count": count, "metadata_path": str(meta_path), "metadata": metadata}
