#!/usr/bin/env python3
"""Sync public works and peer reviews from ORCID.

Required environment variables:
  ORCID_CLIENT_ID
  ORCID_CLIENT_SECRET
Optional:
  ORCID_ID (defaults to Hyung Suk Kim's ORCID)
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT_WORKS = DATA / "publications.json"
OUT_REVIEWS = DATA / "peer_reviews.json"
FEATURED = DATA / "featured.json"
ORCID_ID = os.getenv("ORCID_ID", "0000-0002-9155-1144")
CLIENT_ID = os.getenv("ORCID_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("ORCID_CLIENT_SECRET", "")
API = "https://pub.orcid.org/v3.0"
TOKEN_URL = "https://orcid.org/oauth/token"
UA = "hsk-orcid-site/2.0 (GitHub Pages scholarly profile)"


def request_json(url: str, *, method: str = "GET", headers=None, data=None):
    h = {"User-Agent": UA, "Accept": "application/vnd.orcid+json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, method=method, headers=h, data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def get_token() -> str:
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError("ORCID_CLIENT_ID and ORCID_CLIENT_SECRET must be set as GitHub repository secrets.")
    payload = urllib.parse.urlencode(
        {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "client_credentials",
            "scope": "/read-public",
        }
    ).encode()
    req = urllib.request.Request(
        TOKEN_URL,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": UA,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read().decode("utf-8"))
    return body["access_token"]


def val(x: Any):
    if x is None:
        return None
    if isinstance(x, dict):
        return x.get("value")
    return x


def dig(obj: Any, *path: str):
    cur = obj
    for key in path:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(key)
        elif isinstance(cur, list):
            try:
                cur = cur[int(key)]
            except Exception:
                return None
        else:
            return None
    return cur


def first_value(obj: Any, *paths: tuple[str, ...]):
    for path in paths:
        raw = dig(obj, *path)
        if raw is None:
            continue
        v = val(raw)
        if v not in (None, ""):
            return v
    return None


def to_int(v):
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


# ---- Works ----
def doi_from_external_ids(work):
    ids = ((work.get("external-ids") or {}).get("external-id") or [])
    for item in ids:
        if str(item.get("external-id-type", "")).lower() == "doi":
            return str(item.get("external-id-value") or "").strip().lower() or None
    return None


def url_from_work(work, doi):
    u = val(work.get("url"))
    if u:
        return u
    return f"https://doi.org/{doi}" if doi else None


def authors_from_work(work):
    contribs = ((work.get("contributors") or {}).get("contributor") or [])
    names = []
    for c in contribs:
        name = val(c.get("credit-name"))
        if name:
            names.append(name)
    return names


def year_from_work(work):
    pd = work.get("publication-date") or {}
    return to_int(val(pd.get("year")))


def title_from_work(work):
    wt = work.get("title") or work.get("work-title") or {}
    t = wt.get("title") if isinstance(wt, dict) else None
    return val(t) or "Untitled work"


def journal_from_work(work):
    return val(work.get("journal-title"))


def normalize_work(work, featured_dois):
    doi = doi_from_external_ids(work)
    return {
        "title": title_from_work(work),
        "authors": authors_from_work(work),
        "journal": journal_from_work(work),
        "year": year_from_work(work),
        "doi": doi,
        "url": url_from_work(work, doi),
        "type": work.get("type"),
        "put_code": work.get("put-code"),
        "featured": bool(doi and doi.lower() in featured_dois),
    }


def sync_works(auth):
    summary = request_json(f"{API}/{ORCID_ID}/works", headers=auth)
    groups = summary.get("group") or []
    featured_dois = set()
    if FEATURED.exists():
        featured_dois = {d.lower() for d in json.loads(FEATURED.read_text(encoding="utf-8")).get("dois", [])}

    works = []
    seen = set()
    for g in groups:
        summaries = g.get("work-summary") or []
        if not summaries:
            continue
        s = max(summaries, key=lambda x: ((x.get("last-modified-date") or {}).get("value") or 0))
        put = s.get("put-code")
        if put is None:
            continue
        try:
            detail = request_json(f"{API}/{ORCID_ID}/work/{put}", headers=auth)
        except Exception as e:
            print(f"warning: failed to fetch work put-code {put}: {e}", file=sys.stderr)
            detail = s
        item = normalize_work(detail, featured_dois)
        key = item.get("doi") or f"orcid:{put}"
        if key in seen:
            continue
        seen.add(key)
        works.append(item)

    works.sort(key=lambda p: (p.get("year") or 0, p.get("title") or ""), reverse=True)
    payload = {
        "meta": {
            "orcid": ORCID_ID,
            "last_synced": datetime.now(timezone.utc).isoformat(),
            "source": "ORCID Public API v3.0",
        },
        "publications": works,
    }
    OUT_WORKS.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Synced {len(works)} ORCID works -> {OUT_WORKS.relative_to(ROOT)}")


# ---- Peer reviews ----
def collect_put_codes(node, out: set[int]):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "put-code":
                iv = to_int(v)
                if iv is not None:
                    out.add(iv)
            else:
                collect_put_codes(v, out)
    elif isinstance(node, list):
        for item in node:
            collect_put_codes(item, out)


def issn_from_group_id(group_id):
    """Return a normalized ISSN from an ORCID peer-review group id, if present."""
    if not group_id:
        return None
    m = re.search(r"issn:\s*([0-9Xx]{4})-?([0-9Xx]{4})", str(group_id), flags=re.I)
    if not m:
        return None
    return f"{m.group(1).upper()}-{m.group(2).upper()}"


def resolve_journal_title_from_issn(issn, cache):
    """Resolve an ISSN to a journal title for display.

    ORCID often stores only the ISSN group id plus the publisher as the convening
    organization. Crossref is used only to turn that ISSN into a human-readable
    journal title; ORCID remains the source of the review activity itself.
    """
    if not issn:
        return None
    if issn in cache:
        return cache[issn]
    title = None
    try:
        url = f"https://api.crossref.org/journals/{urllib.parse.quote(issn)}"
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": UA},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            body = json.loads(r.read().decode("utf-8"))
        message = body.get("message") or {}
        raw = message.get("title")
        if isinstance(raw, list):
            title = next((str(x).strip() for x in raw if str(x).strip()), None)
        elif raw:
            title = str(raw).strip()
    except Exception as e:
        print(f"warning: failed to resolve ISSN {issn}: {e}", file=sys.stderr)
    cache[issn] = title
    return title


def normalize_peer_review(pr, journal_cache):
    group_id = first_value(pr, ("review-group-id",))
    issn = issn_from_group_id(group_id)

    # Prefer an explicit journal/container name from ORCID. If it is absent,
    # resolve the ORCID ISSN group id to the journal title. Only then fall back
    # to the convening organization (normally the publisher).
    explicit_outlet = first_value(
        pr,
        ("subject-container-name", "title"),
        ("subject-container-name",),
    )
    resolved_outlet = resolve_journal_title_from_issn(issn, journal_cache)
    organization = first_value(pr, ("convening-organization", "name"), ("organization", "name"))
    outlet = explicit_outlet or resolved_outlet or organization or group_id or "Peer review"

    url = first_value(pr, ("review-url",), ("url",))
    review_type = first_value(pr, ("review-type",), ("type",))
    role = first_value(pr, ("reviewer-role",))
    source_name = first_value(pr, ("source", "source-name"),)

    # ORCID v3.0 uses review-completion-date.
    year = to_int(first_value(pr, ("review-completion-date", "year"),))
    month = to_int(first_value(pr, ("review-completion-date", "month"),))
    day = to_int(first_value(pr, ("review-completion-date", "day"),))

    if year and month and day:
        date_label = f"{year:04d}-{month:02d}-{day:02d}"
    elif year and month:
        date_label = f"{year:04d}-{month:02d}"
    elif year:
        date_label = f"{year:04d}"
    else:
        date_label = None

    return {
        "put_code": pr.get("put-code"),
        "outlet": outlet,
        "organization": organization,
        "review_type": review_type,
        "reviewer_role": role,
        "completion_year": year,
        "completion_month": month,
        "completion_day": day,
        "date_label": date_label,
        "group_id": group_id,
        "issn": issn,
        "url": url,
        "source_name": source_name,
    }

def sync_peer_reviews(auth):
    peer_reviews = []
    journal_cache = {}
    try:
        summary = request_json(f"{API}/{ORCID_ID}/peer-reviews", headers=auth)
        puts: set[int] = set()
        collect_put_codes(summary, puts)
        for put in sorted(puts):
            try:
                detail = request_json(f"{API}/{ORCID_ID}/peer-review/{put}", headers=auth)
            except Exception as e:
                print(f"warning: failed to fetch peer-review put-code {put}: {e}", file=sys.stderr)
                continue
            peer_reviews.append(normalize_peer_review(detail, journal_cache))
    except Exception as e:
        print(f"warning: peer-review sync unavailable: {e}", file=sys.stderr)

    peer_reviews.sort(
        key=lambda x: (
            x.get("completion_year") or 0,
            x.get("completion_month") or 0,
            x.get("completion_day") or 0,
            x.get("outlet") or "",
        ),
        reverse=True,
    )
    payload = {
        "meta": {
            "orcid": ORCID_ID,
            "last_synced": datetime.now(timezone.utc).isoformat(),
            "source": "ORCID Public API v3.0",
        },
        "peer_reviews": peer_reviews,
    }
    OUT_REVIEWS.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Synced {len(peer_reviews)} ORCID peer reviews -> {OUT_REVIEWS.relative_to(ROOT)}")


def main():
    token = get_token()
    auth = {"Authorization": f"Bearer {token}"}
    sync_works(auth)
    sync_peer_reviews(auth)


if __name__ == "__main__":
    main()
