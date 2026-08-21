"""
GitHub Actions Runner / Batch Extractor Script for DoodStream & Playmogo with Full Verbose Debug Logging.

Modes of operation:
1. Batch Mode (Default for GitHub Actions):
   Iterates through merged_movie_streaming_data.json, extracts live direct MP4 stream URLs
   using dedicated residential proxies, and saves to extracted_streams.json.
2. CLI / Single ID Lookup Mode:
   python run_extractor.py --id 81
   python run_extractor.py --id tt0087544
   python run_extractor.py --url https://dood.watch/e/yf1wzl7rq2yv
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import string
import sys
import time
from typing import Dict, Iterable, List, Optional, Tuple, Any
from urllib.parse import urlparse

import requests

try:
    import cloudscraper  # type: ignore
except Exception:
    cloudscraper = None

# Configure logging to print immediately to stdout for GitHub Actions logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("dood_extractor")

# ---------------------------------------------------------------------------
# Config & Mirrors
# ---------------------------------------------------------------------------

MIRRORS = [
    "playmogo.com",
    "dood.watch",
    "dood.so",
    "dood.li",
    "doods.pro",
    "vidply.com",
    "ds2play.com",
    "ds2video.com",
    "d-s.io",
    "d000d.com",
    "d0000d.com",
    "dood.ws",
    "dood.pm",
    "dood.re",
    "dood.to",
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)

BROWSER_HEADERS = {
    "User-Agent": UA,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
    "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    "DNT": "1",
}

# ---------------------------------------------------------------------------
# Dedicated Residential Proxy Pool
# ---------------------------------------------------------------------------

RESIDENTIAL_PROXIES: List[str] = [
    "http://viqhajod:aisg6z1gsn25@31.59.20.176:6754",
    "http://viqhajod:aisg6z1gsn25@31.56.127.193:7684",
    "http://viqhajod:aisg6z1gsn25@45.38.107.97:6014",
    "http://viqhajod:aisg6z1gsn25@198.105.121.200:6462",
    "http://viqhajod:aisg6z1gsn25@64.137.96.74:6641",
    "http://viqhajod:aisg6z1gsn25@198.23.243.226:6361",
    "http://viqhajod:aisg6z1gsn25@38.154.185.97:6370",
    "http://viqhajod:aisg6z1gsn25@84.247.60.125:6095",
    "http://viqhajod:aisg6z1gsn25@142.111.67.146:5611",
    "http://viqhajod:aisg6z1gsn25@191.96.254.138:6185",
]

def get_proxy_dict(proxy_url: str) -> dict:
    return {"http": proxy_url, "https": proxy_url}


def _mask_proxy(p: str) -> str:
    """Mask credentials for safe logging in GitHub Actions."""
    if "@" in p:
        return p.split("@")[-1]
    return p


# ---------------------------------------------------------------------------
# Extractor Logic
# ---------------------------------------------------------------------------

def _video_id(s: str) -> str:
    s = s.strip()
    m = re.search(r"/[ed]/([A-Za-z0-9]+)", s)
    return m.group(1) if m else s


def _make_play(token: str) -> str:
    rnd = "".join(random.choices(string.ascii_letters + string.digits, k=10))
    return f"{rnd}?token={token}&expiry={int(time.time() * 1000)}"


def _build_session(engine: str = "requests", proxy_url: Optional[str] = None):
    if engine == "cloudscraper" and cloudscraper is not None:
        s = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
    else:
        s = requests.Session()

    s.headers.update(BROWSER_HEADERS)
    if proxy_url:
        s.proxies = get_proxy_dict(proxy_url)
    return s


def _try_mirror(session, mirror: str, vid: str, debug_tag: str = "") -> Optional[Tuple[str, str]]:
    url = f"https://{mirror}/e/{vid}"
    try:
        r = session.get(url, timeout=(5, 10), allow_redirects=True)
        has_md5 = "/pass_md5/" in r.text
        logger.info(f"[{debug_tag}] GET {mirror}/e/{vid} -> status={r.status_code}, len={len(r.text)}, pass_md5={has_md5}")
        if r.status_code == 200 and has_md5:
            return str(r.url), r.text
        if r.status_code != 200:
            logger.warning(f"[{debug_tag}] {mirror} returned HTTP {r.status_code} (HTML Snippet: {r.text[:120]!r})")
    except Exception as exc:
        logger.warning(f"[{debug_tag}] Connection error on {mirror}: {exc.__class__.__name__} - {exc}")
        return None
    return None


def _load_player(vid: str, mirrors: Iterable[str]) -> Tuple[Any, str, str]:
    proxies_to_try = list(RESIDENTIAL_PROXIES)
    random.shuffle(proxies_to_try)

    logger.info(f"==> Starting extraction for video_id={vid}")
    logger.info(f"==> Total residential proxies available: {len(proxies_to_try)}")

    # 1. Try with Residential Proxy pool (requests first, then cloudscraper)
    for proxy in proxies_to_try:
        masked = _mask_proxy(proxy)
        for engine in ["requests", "cloudscraper"]:
            if engine == "cloudscraper" and cloudscraper is None:
                continue
            session = _build_session(engine=engine, proxy_url=proxy)
            for m in mirrors[:5]:  # Try top 5 fastest mirrors
                tag = f"{engine} via {masked}"
                hit = _try_mirror(session, m, vid, debug_tag=tag)
                if hit:
                    final_url, html = hit
                    logger.info(f"==> SUCCESS: Mirror {m} matched via proxy {masked}")
                    return session, final_url, html

    # 2. Fallback direct without proxy
    logger.info("==> Trying direct connection without proxies as fallback...")
    for engine in ["cloudscraper", "requests"]:
        if engine == "cloudscraper" and cloudscraper is None:
            continue
        session_direct = _build_session(engine=engine)
        for m in mirrors:
            tag = f"direct {engine}"
            hit = _try_mirror(session_direct, m, vid, debug_tag=tag)
            if hit:
                final_url, html = hit
                logger.info(f"==> SUCCESS: Mirror {m} matched directly without proxy")
                return session_direct, final_url, html

    raise RuntimeError(
        f"All proxies and mirrors failed for video_id={vid!r}. Check debug log above for individual response codes & errors."
    )


def extract_dood(url_or_id: str) -> dict:
    vid = _video_id(url_or_id)
    session, player_url, html = _load_player(vid, MIRRORS)

    parsed = urlparse(player_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    m = re.search(r"\$\.get\(['\"](/pass_md5/[^'\"]+)['\"]", html)
    if not m:
        raise RuntimeError(f"pass_md5 endpoint regex match failed in player HTML from {player_url}.")
    pass_md5_path = m.group(1)
    token = pass_md5_path.rstrip("/").rsplit("/", 1)[-1]

    logger.info(f"Fetching pass_md5 from: {base + pass_md5_path}")
    r2 = session.get(
        base + pass_md5_path,
        headers={
            "Referer": player_url,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "*/*",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        },
        timeout=(5, 10),
    )
    r2.raise_for_status()
    body = r2.text.strip()
    logger.info(f"pass_md5 response body: {body[:60]}...")
    if body == "RELOAD" or not body.startswith("http"):
        raise RuntimeError(f"pass_md5 returned non-URL body: {body!r}")

    direct = body + _make_play(token)
    logger.info(f"Direct stream URL assembled successfully!")

    return {
        "status": "success",
        "video_id": vid,
        "mirror": base,
        "player_page": player_url,
        "pass_md5": base + pass_md5_path,
        "token": token,
        "stream_url": direct,
        "container": "video/mp4",
        "required_headers": {
            "User-Agent": UA,
            "Referer": player_url
        }
    }


def get_dood_url_from_entry(entry: dict) -> Optional[str]:
    dood_domains = (
        "dood", "ds2play", "ds2video", "d000d", "d0000d", "d-s.io", "vidply", "playmogo", "playmongo"
    )
    for k, v in entry.items():
        if isinstance(v, str) and any(d in v.lower() for d in dood_domains):
            return v
    return None


def run_batch_extraction(db_path: str, output_path: str, limit: Optional[int] = None):
    logger.info(f"Starting batch extraction from {db_path}...")
    with open(db_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Filter items that have a Dood / Playmogo host
    dood_items = []
    for item in data:
        dood_url = get_dood_url_from_entry(item)
        if dood_url:
            dood_items.append((item, dood_url))

    logger.info(f"Found {len(dood_items)} items with DoodStream/Playmogo hosts.")
    if limit:
        dood_items = dood_items[:limit]
        logger.info(f"Processing limited set of {limit} items.")

    results = []
    success_count = 0

    for idx, (movie, host_url) in enumerate(dood_items, 1):
        title = movie.get("title")
        tmdb_imdb = movie.get("tmdb/imdb")
        logger.info(f"\n==========================================")
        logger.info(f"[{idx}/{len(dood_items)}] Processing: {title} ({tmdb_imdb}) - {host_url}")
        try:
            extraction = extract_dood(host_url)
            results.append({
                "serial": movie.get("serial"),
                "title": title,
                "tmdb/imdb": tmdb_imdb,
                "source_host": host_url,
                "stream": extraction,
                "extracted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })
            success_count += 1
            logger.info(f"==> SUCCESS for {title}")
        except Exception as e:
            logger.warning(f"==> FAILED for {title}: {e}")
            results.append({
                "serial": movie.get("serial"),
                "title": title,
                "tmdb/imdb": tmdb_imdb,
                "source_host": host_url,
                "status": "failed",
                "error": str(e)
            })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(f"\n==========================================")
    logger.info(f"Extraction completed! {success_count}/{len(dood_items)} succeeded. Saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="DoodStream / Playmogo Stream Extractor")
    parser.add_argument("--db", default="merged_movie_streaming_data.json", help="Path to database JSON")
    parser.add_argument("--out", default="extracted_streams.json", help="Path to output JSON")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of movies to process in batch")
    parser.add_argument("--id", type=str, default=None, help="Extract specific TMDB or IMDB ID")
    parser.add_argument("--url", type=str, default=None, help="Extract specific DoodStream URL")

    args = parser.parse_args()

    if args.url:
        print(json.dumps(extract_dood(args.url), indent=2))
    elif args.id:
        with open(args.db, "r", encoding="utf-8") as f:
            data = json.load(f)
        target_movie = None
        for item in data:
            combo = item.get("tmdb/imdb", "")
            parts = combo.split("/")
            if args.id.lower() == combo.lower() or (len(parts) > 0 and args.id.lower() == parts[0].strip().lower()) or (len(parts) > 1 and args.id.lower() == parts[1].strip().lower()) or args.id == str(item.get("serial")):
                target_movie = item
                break
        if not target_movie:
            logger.error(f"Movie identifier '{args.id}' not found in {args.db}.")
            sys.exit(1)
        dood_url = get_dood_url_from_entry(target_movie)
        if not dood_url:
            logger.error(f"No DoodStream/Playmogo link found in record for '{target_movie.get('title')}'.")
            sys.exit(1)
        logger.info(f"Extracting '{target_movie.get('title')}' ({dood_url})...")
        res = extract_dood(dood_url)
        print("\n=== EXTRACTION RESULT ===")
        print(json.dumps(res, indent=2))
    else:
        run_batch_extraction(args.db, args.out, args.limit)


if __name__ == "__main__":
    main()
