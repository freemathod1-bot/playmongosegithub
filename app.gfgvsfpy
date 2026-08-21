"""
Render-ready FastAPI Web Service for DoodStream / Playmogo Extraction & ID Lookup.

Configured with dedicated residential proxy pool + Cloudscraper:
  - 31.59.20.176:6754 (UK)
  - 31.56.127.193:7684 (US)
  - 45.38.107.97:6014 (UK)
  - 198.105.121.200:6462 (UK)
  - 64.137.96.74:6641 (ES)
  - 198.23.243.226:6361 (US)
  - 38.154.185.97:6370 (US)
  - 84.247.60.125:6095 (PL)
  - 142.111.67.146:5611 (JP)
  - 191.96.254.138:6185 (US)
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import string
import time
from typing import Dict, Iterable, List, Optional, Tuple, Any
from urllib.parse import urlparse

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

try:
    import cloudscraper  # type: ignore
except Exception:
    cloudscraper = None

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dood_api")

app = FastAPI(
    title="DoodStream Video Extractor API",
    description="FastAPI service for looking up movies by TMDB/IMDB and extracting direct stream links with dedicated residential proxy rotation.",
    version="1.2.0",
)

# Enable CORS for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Config & Active Fast Mirrors
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


# ---------------------------------------------------------------------------
# Database In-Memory Cache & Indexing
# ---------------------------------------------------------------------------

DATABASE_FILE = os.getenv("DATABASE_FILE", "merged_movie_streaming_data.json")

tmdb_index: Dict[str, dict] = {}
imdb_index: Dict[str, dict] = {}
combo_index: Dict[str, dict] = {}
all_items_count = 0


def load_database():
    global all_items_count, tmdb_index, imdb_index, combo_index
    if not os.path.exists(DATABASE_FILE):
        logger.warning(f"Database file '{DATABASE_FILE}' not found. Lookup will return empty results.")
        return

    logger.info(f"Loading database from {DATABASE_FILE}...")
    try:
        with open(DATABASE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                logger.error("Invalid database format. Expected JSON array.")
                return

            tmdb_idx = {}
            imdb_idx = {}
            combo_idx = {}

            for item in data:
                combo = item.get("tmdb/imdb", "").strip()
                if combo:
                    combo_idx[combo.lower()] = item
                    parts = combo.split("/")
                    if len(parts) == 2:
                        tmdb_id, imdb_id = parts[0].strip(), parts[1].strip()
                        if tmdb_id:
                            tmdb_idx[tmdb_id.lower()] = item
                        if imdb_id:
                            imdb_idx[imdb_id.lower()] = item
                    elif len(parts) == 1:
                        val = parts[0].strip()
                        if val.startswith("tt"):
                            imdb_idx[val.lower()] = item
                        elif val.isdigit():
                            tmdb_idx[val] = item

            tmdb_index = tmdb_idx
            imdb_index = imdb_idx
            combo_index = combo_idx
            all_items_count = len(data)
            logger.info(
                f"Successfully loaded {all_items_count} items. "
                f"(TMDB Indexed: {len(tmdb_index)}, IMDB Indexed: {len(imdb_index)})"
            )
    except Exception as e:
        logger.error(f"Failed to load database: {e}")


@app.on_event("startup")
def startup_event():
    load_database()


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


def _build_session(engine: str = "cloudscraper", proxy_url: Optional[str] = None):
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


def _try_mirror(session, mirror: str, vid: str) -> Optional[Tuple[str, str]]:
    url = f"https://{mirror}/e/{vid}"
    try:
        r = session.get(url, timeout=(4, 7), allow_redirects=True)
    except requests.RequestException:
        return None
    if r.status_code != 200 or not r.text:
        return None
    if "/pass_md5/" not in r.text:
        return None
    return str(r.url), r.text


def _load_player(vid: str, mirrors: Iterable[str]) -> Tuple[Any, str, str]:
    """
    Combines Cloudscraper with Residential Proxies to guarantee 100% bypass of Cloudflare.
    """
    proxies_to_try = list(RESIDENTIAL_PROXIES)
    random.shuffle(proxies_to_try)

    last_err = None
    engines = ["cloudscraper", "requests"] if cloudscraper is not None else ["requests"]

    # 1. Try with Residential Proxy pool
    for proxy in proxies_to_try:
        for engine in engines:
            session = _build_session(engine=engine, proxy_url=proxy)
            for m in mirrors[:5]:
                hit = _try_mirror(session, m, vid)
                if hit:
                    final_url, html = hit
                    return session, final_url, html
                last_err = m

    # 2. Fallback direct without proxy
    for engine in engines:
        session_direct = _build_session(engine=engine)
        for m in mirrors:
            hit = _try_mirror(session_direct, m, vid)
            if hit:
                final_url, html = hit
                return session_direct, final_url, html
            last_err = m

    raise RuntimeError(
        f"No mirror served the player for id={vid!r}. Last tried: {last_err}."
    )


def extract_dood(url_or_id: str) -> dict:
    vid = _video_id(url_or_id)
    session, player_url, html = _load_player(vid, MIRRORS)

    parsed = urlparse(player_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    m = re.search(r"\$\.get\(['\"](/pass_md5/[^'\"]+)['\"]", html)
    if not m:
        raise RuntimeError("pass_md5 endpoint not present in player HTML.")
    pass_md5_path = m.group(1)
    token = pass_md5_path.rstrip("/").rsplit("/", 1)[-1]

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
        timeout=(4, 8),
    )
    r2.raise_for_status()
    body = r2.text.strip()
    if body == "RELOAD" or not body.startswith("http"):
        raise RuntimeError(f"pass_md5 returned non-URL body: {body!r}")

    direct = body + _make_play(token)

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


def find_in_database(query_id: str) -> Optional[dict]:
    """Finds record in JSON database using TMDB, IMDB, or Combo ID."""
    clean_id = query_id.strip().lower()

    # 1. Exact combo match e.g. 81/tt0087544
    if clean_id in combo_index:
        return combo_index[clean_id]

    # 2. TMDB ID match (if pure numbers)
    if clean_id in tmdb_index:
        return tmdb_index[clean_id]

    # 3. IMDB ID match (e.g. tt0087544)
    if clean_id in imdb_index:
        return imdb_index[clean_id]

    return None


def get_dood_url_from_entry(entry: dict) -> Optional[str]:
    """Inspects all host-* keys in entry for dood.watch or playmogo/playmongo mirrors."""
    dood_domains = (
        "dood", "ds2play", "ds2video", "d000d", "d0000d", "d-s.io", "vidply", "playmogo", "playmongo"
    )
    for k, v in entry.items():
        if isinstance(v, str) and any(d in v.lower() for d in dood_domains):
            return v
    return None


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return {
        "status": "online",
        "service": "DoodStream API Extractor",
        "total_indexed_movies": all_items_count,
        "residential_proxies_configured": len(RESIDENTIAL_PROXIES),
        "examples": [
            "/api/81",
            "/api/tt0087544",
            "/api/81/tt0087544",
            "/api/extract?url=https://dood.watch/e/yf1wzl7rq2yv",
            "/api/lookup/81"
        ]
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "database_loaded": all_items_count > 0,
        "proxies_count": len(RESIDENTIAL_PROXIES)
    }


@app.get("/api/lookup/{query_id:path}")
def lookup_movie(query_id: str):
    """Lookup metadata and host links by TMDB / IMDB ID without running stream extraction."""
    record = find_in_database(query_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Movie with TMDB/IMDB identifier '{query_id}' not found in database."
        )
    return {
        "status": "found",
        "query": query_id,
        "movie": record
    }


@app.get("/api/extract")
def extract_by_url(url: str = Query(..., description="Direct DoodStream or Playmogo URL or File ID")):
    """Directly extracts stream URL from a given DoodStream URL or File ID."""
    try:
        res = extract_dood(url)
        return res
    except Exception as exc:
        logger.error(f"Extraction error for url '{url}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/{query_id:path}")
def api_resolve(query_id: str):
    """
    Unified endpoint:
    - If TMDB/IMDB ID is passed (e.g., 81, tt0087544, 81/tt0087544),
      finds the movie in the database, detects dood/playmogo embed, and extracts stream.
    - If direct URL or file ID is passed, extracts stream directly.
    """
    clean_query = query_id.strip()

    # 1. Check if it's already a direct Dood/Playmogo/mirror link
    if "dood" in clean_query.lower() or "playmogo" in clean_query.lower() or "playmongo" in clean_query.lower() or clean_query.startswith("http"):
        try:
            return extract_dood(clean_query)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to extract stream: {exc}")

    # 2. Lookup in JSON database
    record = find_in_database(clean_query)
    if not record:
        # If not found in DB, try treating query_id as a dood video code if it matches alphanumeric pattern
        if re.match(r"^[A-Za-z0-9]{8,20}$", clean_query):
            try:
                return extract_dood(clean_query)
            except Exception:
                pass
        raise HTTPException(
            status_code=404,
            detail=f"Identifier '{clean_query}' not found in database."
        )

    # 3. Detect dood / playmogo host from the record
    dood_url = get_dood_url_from_entry(record)
    if not dood_url:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "Found movie in database, but it does not have a DoodStream or Playmogo host link.",
                "movie": record
            }
        )

    # 4. Extract direct stream URL
    try:
        extraction = extract_dood(dood_url)
        return {
            "status": "success",
            "title": record.get("title"),
            "serial": record.get("serial"),
            "tmdb_imdb": record.get("tmdb/imdb"),
            "source_host": dood_url,
            "stream": extraction
        }
    except Exception as exc:
        logger.error(f"Extraction error for movie '{record.get('title')}' ({dood_url}): {exc}")
        raise HTTPException(
            status_code=502,
            detail=f"Extracted host '{dood_url}' failed to resolve stream: {exc}"
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
