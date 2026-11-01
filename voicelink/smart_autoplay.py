"""Smart Era- & Vibe-Aware Autoplay Engine for Vocard."""

from __future__ import annotations

import random
import re
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .player import Player
    from .objects import Track

ERA_POOLS: dict[str, list[str]] = {
    "indo_modern": [
        "Bernadya - Satu Bulan",
        "Bernadya - Untungnya, Hidup Harus Tetap Berjalan",
        "Bernadya - Kata Mereka Ini Berlebihan",
        "Bernadya - Apa Mungkin",
        "Bernadya - Kini Mereka Tahu",
        "Hindia - Evaluasi",
        "Hindia - Cincin",
        "Hindia - Rumah Ke Rumah",
        "Hindia - Secukupnya",
        "Hindia - Membasuh",
        "Hindia - Kita Ke Sana",
        "rumahsakit - Panasea",
        "rumahsakit - Kuning",
        "rumahsakit - Hilang",
        "Alkateri - Egosentris",
        "Perunggu - 33x",
        "Perunggu - Ini Abadi",
        "Perunggu - Pastikan Riuh Akhiri Malammu",
        ".Feast - Nina",
        ".Feast - Peradaban",
        "Lomba Sihir - Hati dan Paru-Paru",
        "Juicy Luicy - Sialan",
        "Juicy Luicy - Lampu Kuning",
        "Juicy Luicy - Tampar",
        "Juicy Luicy - Lantas",
        "Sal Priadi - Gala Bunga Matahari",
        "Sal Priadi - Dari Planet Lain",
        "Sal Priadi - Serta Mulia",
        "Nadin Amizah - Rayuan Perempuan Gila",
        "Nadin Amizah - Bertaut",
        "Nadin Amizah - Semua Aku Dirayakan",
        "Mahalini - Sial",
        "Mahalini - Mati-Matian",
        "Tiara Andini - Kupu-Kupu",
        "Lyodra - Pesan Terakhir",
        "Tulus - Hati-Hati di Jalan",
        "Tulus - Monokrom",
        "Tulus - Interaksi",
        "Raim Laode - Komang",
        "Pamungkas - To The Bone",
        "Reality Club - Anything You Want",
        "Reality Club - Alexandra",
        "For Revenge - Serana",
        "For Revenge - Jakarta Hari Ini",
        "Payung Teduh - Akad",
        "Payung Teduh - Resah",
        "Fourtwnty - Zona Nyaman",
        "Fourtwnty - Fana Merah Jambu",
        "Danilla - Senja di Ambang Pilu",
        "Barasuara - Terbuang Dalam Waktu",
    ],
    "indo_nostalgia": [
        "Sheila On 7 - Dan",
        "Sheila On 7 - Seberapa Pantas",
        "Sheila On 7 - Sephia",
        "Sheila On 7 - Hari Bersamanya",
        "Sheila On 7 - Anugerah Terindah Yang Pernah Kumiliki",
        "Dewa 19 - Kangen",
        "Dewa 19 - Pupus",
        "Dewa 19 - Risalah Hati",
        "Dewa 19 - Separuh Nafas",
        "Dewa 19 - Roman Picisan",
        "Peterpan - Semua Tentang Kita",
        "Peterpan - Yang Terdalam",
        "Peterpan - Ada Apa Denganmu",
        "NOAH - Separuh Aku",
        "Andra & The BackBone - Sempurna",
        "Padi - Kasih Tak Sampai",
        "Padi - Sobat",
        "Kerispatih - Mengenangmu",
        "Kerispatih - Tapi Bukan Aku",
        "Nidji - Laskar Pelangi",
        "Nidji - Hapus Aku",
        "Letto - Ruang Rindu",
        "Letto - Sebelum Cahaya",
        "Ada Band - Manusia Bodoh",
        "Samsons - Kenangan Terindah",
        "Ungu - Demi Waktu",
        "Vierratale - Seandainya",
        "Last Child - Duka",
        "Efek Rumah Kaca - Desember",
    ],
    "global_modern": [
        "Lady Gaga Bruno Mars - Die With A Smile",
        "Billie Eilish - BIRDS OF A FEATHER",
        "Billie Eilish - WILDFLOWER",
        "Sabrina Carpenter - Espresso",
        "Sabrina Carpenter - Please Please Please",
        "The Weeknd - Blinding Lights",
        "The Weeknd - Starboy",
        "The Weeknd - Die For You",
        "The Weeknd - Save Your Tears",
        "Harry Styles - As It Was",
        "Taylor Swift - Cruel Summer",
        "Olivia Rodrigo - vampire",
        "Olivia Rodrigo - drivers license",
        "SZA - Kill Bill",
        "SZA - Snooze",
        "Post Malone - Circles",
        "Post Malone - Sunflower",
        "Dua Lipa - Levitating",
        "Cigarettes After Sex - Apocalypse",
        "Cigarettes After Sex - Sunsetz",
        "Arctic Monkeys - I Wanna Be Yours",
        "Arctic Monkeys - 505",
        "The Neighbourhood - Sweater Weather",
        "Joji - Glimpse of Us",
        "Joji - Slow Dancing in the Dark",
        "d4vd - Here With Me",
        "d4vd - Romantic Homicide",
        "Daniel Caesar - Best Part",
        "wave to earth - seasons",
        "wave to earth - bad",
        "keshi - LIMBO",
        "Laufey - From The Start",
    ],
    "global_throwback": [
        "Coldplay - Yellow",
        "Coldplay - Viva La Vida",
        "Coldplay - The Scientist",
        "Coldplay - Fix You",
        "Coldplay - Sparks",
        "Linkin Park - In the End",
        "Linkin Park - Numb",
        "Maroon 5 - Payphone",
        "Maroon 5 - Sugar",
        "Maroon 5 - She Will Be Loved",
        "OneRepublic - Counting Stars",
        "Imagine Dragons - Demons",
        "Imagine Dragons - Believer",
        "Paramore - Still Into You",
        "Bruno Mars - Locked Out of Heaven",
        "Bruno Mars - When I Was Your Man",
        "Bruno Mars - Just the Way You Are",
        "Bruno Mars - That's What I Like",
        "Adele - Someone Like You",
        "Ed Sheeran - Perfect",
        "Avicii - Wake Me Up",
        "The Chainsmokers - Closer",
        "Oasis - Don't Look Back In Anger",
        "Radiohead - Creep",
    ],
    "asian_hits": [
        "ROSE Bruno Mars - APT.",
        "ILLIT - Magnetic",
        "NewJeans - Ditto",
        "NewJeans - Hype Boy",
        "NewJeans - Super Shy",
        "LE SSERAFIM - Perfect Night",
        "IVE - I AM",
        "aespa - Supernova",
        "Jung Kook - Seven",
        "Fujii Kaze - Shinunoga E-Wa",
        "imase - NIGHT DANCER",
        "YOASOBI - Idol",
        "YOASOBI - Yoru ni Kakeru",
        "Kenshi Yonezu - Kick Back",
        "Official HIGE DANdism - Pretender",
        "RADWIMPS - Sparkle",
        "LiSA - Gurenge",
    ],
}

INDO_KEYWORDS = {
    "bernadya", "hindia", "rumahsakit", "alkateri", "perunggu", "feast", "lomba sihir",
    "juicy luicy", "sal priadi", "nadin amizah", "mahalini", "tiara andini", "lyodra",
    "tulus", "raim laode", "pamungkas", "reality club", "for revenge", "payung teduh",
    "fourtwnty", "danilla", "barasuara", "sheila on 7", "dewa 19", "peterpan", "noah",
    "andra", "padi", "kerispatih", "nidji", "letto", "ada band", "samsons", "ungu",
    "vierratale", "last child", "efek rumah kaca", "rizky febian", "rossa", "raisa",
    "isyana", "fiersa besari", "kunto aji", "virgoun", "armada", "wali", "st12",
    "aku", "kau", "kamu", "yang", "dan", "di", "ke", "hati", "cinta", "rindu", "malam",
    "pulang", "rumah", "bulan", "lirik", "indonesia",
}


def _norm(text: str) -> str:
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", (text or "").lower())
    t = re.sub(r"\b(official|music|video|audio|lyric|lyrics|lirik|mv|hd|4k|visualizer|topic)\b", " ", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def detect_era_pool(track: Optional["Track"]) -> str:
    """Detect the best matching era/vibe pool for a given seed track."""
    if not track:
        return random.choice(["indo_modern", "global_modern"])

    combined = f"{track.author} {track.title}".lower()

    for pool_name, songs in ERA_POOLS.items():
        for s in songs:
            artist_part = s.split(" - ")[0].lower()
            if artist_part in combined:
                return pool_name

    words = set(re.findall(r"[a-z0-9]+", combined))
    if words & INDO_KEYWORDS or any(k in combined for k in ("sheila", "dewa", "peterpan", "kerispatih", "letto")):
        if any(k in combined for k in ("sheila", "dewa", "peterpan", "noah", "padi", "kerispatih", "letto", "nidji", "ada band", "ungu", "samsons")):
            return "indo_nostalgia"
        return "indo_modern"

    if any(k in combined for k in ("yoasobi", "newjeans", "illit", "aespa", "ive", "fujii", "imase", "kenshi", "radwimps", "lisa", "bts", "blackpink")):
        return "asian_hits"

    if any(k in combined for k in ("coldplay", "linkin park", "maroon 5", "oasis", "radiohead", "paramore", "green day", "avicii", "adele")):
        return "global_throwback"

    return random.choice(["indo_modern", "global_modern"])


async def fetch_smart_recommendations(player: "Player", seed_track: Optional["Track"] = None, count: int = 2) -> List["Track"]:
    """
    Fast, smart era-aware recommendation engine.
    Selects the best tracks matching the current era/vibe + YouTube Music radio without duplicates.
    """
    node = player._node
    if not node or not node._available:
        return []

    history_tracks = list(player.queue.history(incTrack=True)) + list(player.queue.tracks())
    if player.current:
        history_tracks.append(player.current)

    seen_norms: set[str] = set()
    seen_ids: set[str] = set()
    for t in history_tracks[-30:]:
        if t.identifier:
            seen_ids.add(t.identifier)
        seen_norms.add(_norm(f"{t.author} {t.title}"))
        seen_norms.add(_norm(t.title))

    if not seed_track and history_tracks:
        seed_track = history_tracks[-1]

    primary_pool_name = detect_era_pool(seed_track)
    # Companion pool for variety within the same cultural/era vibe
    companion_map = {
        "indo_modern": ["indo_modern", "indo_nostalgia", "global_modern"],
        "indo_nostalgia": ["indo_nostalgia", "indo_modern"],
        "global_modern": ["global_modern", "global_throwback", "indo_modern"],
        "global_throwback": ["global_throwback", "global_modern"],
        "asian_hits": ["asian_hits", "global_modern", "indo_modern"],
    }
    pool_choices = companion_map.get(primary_pool_name, ["indo_modern", "global_modern"])

    candidate_queries: list[str] = []
    # Mix 70% primary era pool + 30% companion era pool
    primary_songs = list(ERA_POOLS.get(primary_pool_name, ERA_POOLS["indo_modern"]))
    random.shuffle(primary_songs)

    other_pool_name = random.choice(pool_choices)
    other_songs = list(ERA_POOLS.get(other_pool_name, ERA_POOLS["global_modern"]))
    random.shuffle(other_songs)

    for song_q in primary_songs + other_songs:
        title_part = song_q.split(" - ", 1)[-1]
        if _norm(song_q) not in seen_norms and _norm(title_part) not in seen_norms:
            candidate_queries.append(song_q)
        if len(candidate_queries) >= count + 3:
            break

    results: List["Track"] = []
    requester = node.bot.user

    for q in candidate_queries:
        if len(results) >= count:
            break
        try:
            tracks = await node.get_tracks(f"ytmsearch:{q}", requester=requester)
            if not tracks:
                continue
            if hasattr(tracks, "tracks"):
                tracks = tracks.tracks
            for tr in tracks[:3]:
                # Skip overly long compilations (> 8.5 mins) or live streams
                if tr.is_stream or (tr.length and tr.length > 510_000):
                    continue
                norm_title = _norm(tr.title)
                norm_full = _norm(f"{tr.author} {tr.title}")
                if tr.identifier in seen_ids or norm_title in seen_norms or norm_full in seen_norms:
                    continue
                seen_ids.add(tr.identifier)
                seen_norms.add(norm_title)
                seen_norms.add(norm_full)
                results.append(tr)
                break
        except Exception:
            continue

    return results

