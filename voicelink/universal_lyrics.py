"""Universal Multi-Provider Lyrics Engine with Parallel Fetch & Instant Pre-Cache."""

import asyncio
import aiohttp
import random
import re
import json
import urllib.parse
import bs4

from urllib.parse import quote
from typing import Optional, Any

_LYRICS_CACHE: dict[str, dict[str, Any]] = {}
_INFLIGHT_TASKS: dict[str, asyncio.Task] = {}
_SHARED_SESSION: Optional[aiohttp.ClientSession] = None


async def _get_session() -> aiohttp.ClientSession:
    global _SHARED_SESSION
    if _SHARED_SESSION is None or _SHARED_SESSION.closed:
        connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=600)
        _SHARED_SESSION = aiohttp.ClientSession(connector=connector)
    return _SHARED_SESSION

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
]


def clean_lyrics_queries(title: str, artist: str = "") -> list[str]:
    """Generate clean search queries by stripping noisy YouTube/Spotify tags."""
    raw_title = (title or "").strip()
    raw_artist = (artist or "").strip()

    t = re.sub(r"\(.*?\)|\[.*?\]", " ", raw_title)
    t = re.sub(
        r"\b(official|music|video|audio|lyric|lyrics|lirik|mv|hd|4k|visualizer|live|session|remastered|full|album|version|ost|soundtrack|karaoke|instrumental)\b",
        " ",
        t,
        flags=re.I,
    )
    t = re.sub(r"\b(feat\.?|ft\.?)\b.*", " ", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" -|:•~")

    a = re.sub(r"\(.*?\)|\[.*?\]", " ", raw_artist)
    a = re.sub(
        r"\b(topic|official|vevo|lirik|lyrics|music|channel|records|indonesia|indo|media|entertainment|cosmic)\b",
        " ",
        a,
        flags=re.I,
    )
    a = re.sub(r"\s+", " ", a).strip(" -|:•~")

    queries: list[str] = []
    if a and t and a.lower() not in t.lower() and len(a) > 1:
        queries.append(f"{a} {t}")
        queries.append(f"{t} {a}")
    if t:
        queries.append(t)
    if "-" in raw_title:
        parts = [
            re.sub(
                r"\b(official|music|video|audio|lyric|lyrics|lirik|mv|hd|4k)\b",
                " ",
                re.sub(r"\(.*?\)|\[.*?\]", " ", p),
                flags=re.I,
            ).strip()
            for p in raw_title.split("-", 1)
        ]
        if len(parts) == 2 and parts[0] and parts[1]:
            queries.append(f"{parts[0]} {parts[1]}")
            queries.append(parts[1])
    if raw_title and raw_title not in queries:
        queries.append(raw_title)

    seen = set()
    result = []
    for q in queries:
        q_clean = re.sub(r"\s+", " ", q).strip()
        if q_clean and q_clean.lower() not in seen:
            seen.add(q_clean.lower())
            result.append(q_clean)
    return result


def parse_lrc_lines(synced_text: str) -> list[dict[str, Any]]:
    """Parse LRC timestamped lyrics ([mm:ss.xx] text) into sorted ms entries."""
    if not synced_text:
        return []
    entries = []
    pattern = re.compile(r"\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\](.*)")
    for line in synced_text.splitlines():
        m = pattern.match(line.strip())
        if m:
            mins = int(m.group(1))
            secs = int(m.group(2))
            frac = m.group(3) or "0"
            ms_part = int(frac.ljust(3, "0")[:3])
            total_ms = (mins * 60 + secs) * 1000 + ms_part
            text = m.group(4).strip()
            if text:
                entries.append({"time": total_ms, "text": text})
    entries.sort(key=lambda x: x["time"])
    return entries


def split_lyrics_sections(lyrics_text: str) -> dict[str, str]:
    """Split lyrics text into named sections if [Verse]/[Chorus] headers exist, else {'default': text}."""
    if not lyrics_text or not lyrics_text.strip():
        return {}
    text = lyrics_text.strip()
    parts = re.split(
        r"(\[(?:Verse|Chorus|Pre-Chorus|Bridge|Intro|Outro|Hook|Refrain|Instrumental|Bait|Reff)[^\]]*\])",
        text,
        flags=re.I,
    )
    if len(parts) > 2:
        sections: dict[str, str] = {}
        current_key = "Intro"
        buf = []
        for part in parts:
            part_s = part.strip()
            if not part_s:
                continue
            if part_s.startswith("[") and part_s.endswith("]"):
                if buf:
                    sections[current_key] = "\n".join(buf).strip()
                    buf = []
                header = part_s[1:-1].strip()
                base_header = header[:40]
                idx = 2
                candidate = base_header
                while candidate in sections:
                    candidate = f"{base_header} ({idx})"
                    idx += 1
                current_key = candidate
            else:
                buf.append(part_s)
        if buf:
            sections[current_key] = "\n".join(buf).strip()
        if sections:
            return {"default": text, **sections}
    return {"default": text}


async def _fetch_lrclib(session: aiohttp.ClientSession, queries: list[str]) -> Optional[dict[str, Any]]:
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    for q in queries[:3]:
        try:
            async with session.get(
                "https://lrclib.net/api/search",
                params={"q": q},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json()
                if not isinstance(data, list) or not data:
                    continue
                for item in data:
                    plain = (item.get("plainLyrics") or "").strip()
                    synced = (item.get("syncedLyrics") or "").strip()
                    if plain or synced:
                        if not plain and synced:
                            plain = "\n".join(x["text"] for x in parse_lrc_lines(synced))
                        return {
                            "title": item.get("trackName") or q,
                            "artist": item.get("artistName") or "",
                            "source": "LRCLIB",
                            "plain": plain,
                            "synced": parse_lrc_lines(synced),
                        }
        except Exception:
            continue
    return None


def _parse_genius_html(html: str) -> str:
    soup = bs4.BeautifulSoup(html, "html.parser")
    containers = soup.find_all("div", attrs={"data-lyrics-container": "true"})
    if not containers:
        return ""

    blocks = []
    for c in containers:
        for excluded in c.find_all(attrs={"data-exclude-from-selection": "true"}):
            excluded.decompose()
        for br in c.find_all("br"):
            br.replace_with("\n")
        blocks.append(c.get_text())

    plain = "\n".join(blocks).strip()
    return re.sub(r"^\d*\s*Contributors.*?Lyrics\s*", "", plain, flags=re.I | re.S).strip()


async def _fetch_genius_public(session: aiohttp.ClientSession, queries: list[str]) -> Optional[dict[str, Any]]:
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    for q in queries[:3]:
        try:
            search_url = f"https://genius.com/api/search/multi?q={quote(q)}"
            async with session.get(search_url, headers=headers, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json()

            sections = data.get("response", {}).get("sections", [])
            song_info = None
            for sec in sections:
                if sec.get("type") in ("top_hit", "song"):
                    for hit in sec.get("hits", []):
                        if hit.get("type") == "song":
                            res = hit.get("result", {})
                            if res.get("url") and res.get("lyrics_state") == "complete":
                                song_info = res
                                break
                if song_info:
                    break

            if not song_info:
                continue

            async with session.get(song_info["url"], headers=headers, timeout=aiohttp.ClientTimeout(total=6)) as resp2:
                if resp2.status != 200:
                    continue
                html = await resp2.text()

            plain = await asyncio.to_thread(_parse_genius_html, html)
            if plain:
                return {
                    "title": song_info.get("title") or q,
                    "artist": song_info.get("artist_names") or "",
                    "source": "Genius",
                    "plain": plain,
                    "synced": [],
                }
        except Exception:
            continue
    return None


async def _fetch_netease(session: aiohttp.ClientSession, queries: list[str]) -> Optional[dict[str, Any]]:
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": "https://music.163.com",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    for q in queries[:2]:
        try:
            body = urllib.parse.urlencode({"s": q, "type": 1, "limit": 3, "offset": 0})
            async with session.post(
                "https://music.163.com/api/search/get",
                data=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status != 200:
                    continue
                data = json.loads(await resp.text())
            songs = data.get("result", {}).get("songs", [])
            if not songs:
                continue
            song = songs[0]
            sid = song.get("id")
            async with session.get(
                f"https://music.163.com/api/song/lyric?id={sid}&lv=1&kv=1&tv=-1",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp2:
                if resp2.status != 200:
                    continue
                lrc_data = json.loads(await resp2.text())
            raw_lrc = (lrc_data.get("lrc", {}).get("lyric") or "").strip()
            if not raw_lrc:
                continue
            synced = parse_lrc_lines(raw_lrc)
            plain = "\n".join(x["text"] for x in synced) if synced else re.sub(r"\[.*?\]", "", raw_lrc).strip()
            if plain and len(plain) > 40:
                artists = ", ".join(a.get("name", "") for a in song.get("artists", []) if a.get("name"))
                return {
                    "title": song.get("name") or q,
                    "artist": artists,
                    "source": "NetEase LRC",
                    "plain": plain,
                    "synced": synced,
                }
        except Exception:
            continue
    return None


async def _fetch_lyrist(session: aiohttp.ClientSession, title: str, artist: str, queries: list[str]) -> Optional[dict[str, Any]]:
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    clean_t = queries[1] if len(queries) > 1 else (queries[0] if queries else title)
    clean_a = re.sub(r"\b(topic|official|vevo|lirik|lyrics|cosmic)\b", "", artist or "", flags=re.I).strip()

    for url in [
        f"https://lyrist.vercel.app/api/{quote(clean_t)}/{quote(clean_a)}" if clean_a else None,
        f"https://lyrist.vercel.app/api/{quote(clean_t)}",
    ]:
        if not url:
            continue
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    lyr = (data.get("lyrics") or "").strip()
                    if lyr:
                        return {
                            "title": data.get("title") or clean_t,
                            "artist": data.get("artist") or clean_a,
                            "source": "Lyrist",
                            "plain": lyr,
                            "synced": [],
                        }
        except Exception:
            continue
    return None


def _cache_key(queries: list[str]) -> str:
    return queries[0].lower().strip() if queries else ""


async def _fetch_all_parallel(title: str, artist: str, queries: list[str]) -> Optional[dict[str, Any]]:
    session = await _get_session()

    # Run LRCLIB, Genius Public Search, and NetEase LRC concurrently for minimal latency
    lrc_task = asyncio.create_task(_fetch_lrclib(session, queries))
    gen_task = asyncio.create_task(_fetch_genius_public(session, queries))
    net_task = asyncio.create_task(_fetch_netease(session, queries))

    results = await asyncio.gather(lrc_task, gen_task, net_task, return_exceptions=True)
    lrc_res = results[0] if isinstance(results[0], dict) else None
    gen_res = results[1] if isinstance(results[1], dict) else None
    net_res = results[2] if isinstance(results[2], dict) else None

    # Prefer Genius if it has structured [Verse]/[Chorus] sections, else LRCLIB, else NetEase
    best: Optional[dict[str, Any]] = None
    if gen_res and gen_res.get("plain") and "[" in gen_res["plain"]:
        best = gen_res
        if (lrc_res and lrc_res.get("synced")) or (net_res and net_res.get("synced")):
            best["synced"] = (lrc_res or net_res).get("synced", [])
    elif lrc_res and lrc_res.get("plain"):
        best = lrc_res
    elif gen_res and gen_res.get("plain"):
        best = gen_res
        if net_res and net_res.get("synced"):
            best["synced"] = net_res["synced"]
    elif net_res and net_res.get("plain"):
        best = net_res

    if not best:
        lyr_res = await _fetch_lyrist(session, title, artist, queries)
        if lyr_res and lyr_res.get("plain"):
            best = lyr_res

    if best and best.get("plain"):
        best["sections"] = split_lyrics_sections(best["plain"])
        return best

    return None


async def get_full_lyrics_data(title: str, artist: str = "") -> Optional[dict[str, Any]]:
    """
    Universal multi-provider lyrics fetcher with RAM cache & in-flight deduplication.
    Returns dict with keys: title, artist, source, plain, synced, sections.
    """
    queries = clean_lyrics_queries(title, artist)
    if not queries:
        return None

    key = _cache_key(queries)
    if key in _LYRICS_CACHE:
        return _LYRICS_CACHE[key]

    if key in _INFLIGHT_TASKS:
        try:
            return await _INFLIGHT_TASKS[key]
        except Exception:
            pass

    task = asyncio.create_task(_fetch_all_parallel(title, artist, queries))
    _INFLIGHT_TASKS[key] = task
    try:
        res = await task
        if res and res.get("plain"):
            if len(_LYRICS_CACHE) > 300:
                oldest = next(iter(_LYRICS_CACHE))
                _LYRICS_CACHE.pop(oldest, None)
            _LYRICS_CACHE[key] = res
        return res
    finally:
        _INFLIGHT_TASKS.pop(key, None)


def prefetch_lyrics(title: str, artist: str = "") -> None:
    """Fire-and-forget background task to pre-warm lyrics cache as soon as a song plays."""
    if not title:
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(get_full_lyrics_data(title, artist))
    except Exception:
        pass


class UniversalLyricsPlatform:
    async def get_lyrics(self, title: str, artist: str) -> Optional[dict[str, str]]:
        data = await get_full_lyrics_data(title, artist)
        if not data or not data.get("plain"):
            return None
        return data.get("sections") or {"default": data["plain"]}


