import asyncio
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import requests

from .metadata import TrackState, is_remote_url, joined_artists, local_art_url
from .text import (
    contains_meaningful_text,
    normalize_query_text,
    strip_bracketed_text,
    text_similarity,
    unique_nonempty,
)


VERSION_TAG_PATTERNS: dict[str, tuple[str, ...]] = {
    "remix": (r"\bremix\b", r"\u30ea\u30df\u30c3\u30af\u30b9"),
    "bootleg": (r"\bbootleg\b",),
    "tv_size": (r"\btv\s*size\b", r"\btv\s*version\b", r"\u30c6\u30ec\u30d3\u30b5\u30a4\u30ba"),
    "cover": (r"\bcover\b", r"\u30ab\u30d0\u30fc", r"\u7ffb\u81ea", r"\u7ffb\u5531"),
    "live": (r"\blive\b", r"\u30e9\u30a4\u30d6"),
    "instrumental": (r"\binstrumental\b", r"\binst\.?\b", r"\boff\s*vocal\b", r"\u30a4\u30f3\u30b9\u30c8", r"\u4f34\u594f"),
    "piano": (r"\bpiano\b", r"\u30d4\u30a2\u30ce"),
}


def version_tags(value: str) -> set[str]:
    value = value.casefold()
    return {
        tag
        for tag, patterns in VERSION_TAG_PATTERNS.items()
        if any(re.search(pattern, value) for pattern in patterns)
    }


class AlbumArtResolver:
    def __init__(self, cache_dir: Path, sources: list[str], max_art_cache_items: int = 10) -> None:
        self.cache_dir = cache_dir
        self.art_dir = cache_dir / "art"
        self.art_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = cache_dir / "art-cache.json"
        self.max_art_cache_items = max(1, max_art_cache_items)
        self.sources = sources
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
                ),
                "Referer": "https://y.qq.com/",
            }
        )
        self.memory_cache: dict[tuple[str, str], str] = {}

    async def resolve(self, state: TrackState) -> str:
        original = local_art_url(state.original_art_url)
        if original:
            if is_remote_url(original):
                downloaded = await asyncio.to_thread(self.download_art_url, original)
                return downloaded or original
            return original

        if not state.title:
            return ""

        cache_key = (state.title, joined_artists(state.artists))
        if cache_key in self.memory_cache:
            art_url = self.memory_cache[cache_key]
            self.touch_cached_art_url(art_url)
            return art_url

        url = await asyncio.to_thread(self.find_art_url, state.title, state.artists)
        if not url:
            self.memory_cache[cache_key] = ""
            return ""

        downloaded = await asyncio.to_thread(self.download_art_url, url)
        self.memory_cache[cache_key] = downloaded
        return downloaded

    def read_cache_manifest(self) -> dict[str, dict[str, Any]]:
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except Exception as exc:
            logging.debug("failed to read art cache manifest: %s", exc)
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(key): value for key, value in data.items() if isinstance(value, dict)}

    def write_cache_manifest(self, manifest: dict[str, dict[str, Any]]) -> None:
        tmp = self.manifest_path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            tmp.replace(self.manifest_path)
        except Exception as exc:
            logging.debug("failed to write art cache manifest: %s", exc)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    def record_art_access(self, url: str, target: Path) -> None:
        digest = target.stem
        now = time.time()
        manifest = self.read_cache_manifest()
        entry = manifest.get(digest, {})
        manifest[digest] = {
            "url": url or entry.get("url", ""),
            "file": target.name,
            "created_at": entry.get("created_at", now),
            "accessed_at": now,
        }
        self.prune_art_cache(manifest)

    def touch_cached_art_url(self, art_url: str) -> None:
        if not art_url.startswith("file://"):
            return
        parsed = urlparse(art_url)
        try:
            target = Path(unquote(parsed.path)).resolve()
            if target.parent == self.art_dir.resolve() and target.exists():
                self.record_art_access("", target)
        except OSError:
            return

    def prune_art_cache(self, manifest: dict[str, dict[str, Any]]) -> None:
        for target in self.art_dir.glob("*.jpg"):
            digest = target.stem
            if digest in manifest:
                continue
            try:
                accessed_at = target.stat().st_mtime
            except OSError:
                continue
            manifest[digest] = {
                "url": "",
                "file": target.name,
                "created_at": accessed_at,
                "accessed_at": accessed_at,
            }

        live_entries: list[tuple[str, dict[str, Any], Path]] = []
        for digest, entry in list(manifest.items()):
            target = self.art_dir / str(entry.get("file") or f"{digest}.jpg")
            if not target.exists():
                manifest.pop(digest, None)
                continue
            live_entries.append((digest, entry, target))

        live_entries.sort(key=lambda item: self.cache_entry_accessed_at(item[1]), reverse=True)
        for digest, _entry, target in live_entries[self.max_art_cache_items :]:
            try:
                target.unlink(missing_ok=True)
                logging.debug("pruned old art cache file=%s", target)
            except OSError as exc:
                logging.debug("failed to prune art cache file=%s error=%s", target, exc)
            manifest.pop(digest, None)

        self.write_cache_manifest(manifest)

    def cache_entry_accessed_at(self, entry: dict[str, Any]) -> float:
        try:
            return float(entry.get("accessed_at") or 0)
        except (TypeError, ValueError):
            return 0

    def find_art_url(self, title: str, artists: list[str]) -> str:
        if "qqmusic" in self.sources:
            url = self.find_qqmusic_art(title, artists)
            if url:
                return url
            logging.debug("qqmusic art not found; skipping non-qqmusic fallback")
            return ""

        for source in self.sources:
            if source == "itunes":
                url = self.find_itunes_art(title, artists)
            else:
                continue
            if url:
                return url
        return ""

    def qqmusic_queries(self, title: str, artists: list[str]) -> list[str]:
        plain_title = strip_bracketed_text(title)
        artist_values = unique_nonempty(
            [joined_artists(artists).replace(",", " "), artists[0] if artists else ""]
        )
        queries: list[str] = []
        for artist in artist_values:
            queries.extend([f"{title} {artist}", f"{plain_title} {artist}"])
        queries.extend([title, plain_title])
        return unique_nonempty(queries)

    def qqmusic_song_titles(self, song: dict[str, Any]) -> list[str]:
        return unique_nonempty(
            [
                str(song.get("title") or ""),
                str(song.get("songname") or ""),
                str(song.get("name") or ""),
                str(song.get("fsong") or ""),
            ]
        )

    def qqmusic_song_artists(self, song: dict[str, Any]) -> list[str]:
        singers = song.get("singer", [])
        if isinstance(singers, list):
            return unique_nonempty([str(singer.get("name") or singer.get("title") or "") for singer in singers])
        return unique_nonempty([str(song.get("fsinger") or "")])

    def qqmusic_display_title(self, song: dict[str, Any]) -> str:
        return str(song.get("title") or song.get("songname") or song.get("name") or song.get("fsong") or "")

    def qqmusic_album_mid(self, song: dict[str, Any]) -> str:
        album = song.get("album", {}) if isinstance(song.get("album"), dict) else {}
        value = album.get("mid") or album.get("pmid") or song.get("albummid") or song.get("albumMid")
        if not value:
            return ""
        return str(value).split("_", 1)[0]

    def qqmusic_song_score(self, song: dict[str, Any], title: str, artists: list[str]) -> int:
        target_tags = version_tags(title)
        candidate_tags = version_tags(self.qqmusic_display_title(song))
        if candidate_tags - target_tags:
            logging.debug(
                "qqmusic candidate rejected by version tags title=%r tags=%s target_tags=%s",
                self.qqmusic_display_title(song),
                sorted(candidate_tags),
                sorted(target_tags),
            )
            return 0

        target_title = normalize_query_text(title)
        plain_title = normalize_query_text(strip_bracketed_text(title))
        title_score = 0

        for candidate in self.qqmusic_song_titles(song):
            normalized = normalize_query_text(candidate)
            if normalized == target_title:
                title_score = max(title_score, 100)
            elif plain_title and normalized == plain_title:
                title_score = max(title_score, 90)
            elif contains_meaningful_text(target_title, normalized) or contains_meaningful_text(
                normalized, target_title
            ):
                title_score = max(title_score, 80)
            elif text_similarity(candidate, title) >= 0.88:
                title_score = max(title_score, 75)

        if title_score == 0:
            return 0

        wanted_artists = [normalize_query_text(artist) for artist in artists if normalize_query_text(artist)]
        found_artists = [
            normalize_query_text(artist)
            for artist in self.qqmusic_song_artists(song)
            if normalize_query_text(artist)
        ]
        artist_score = 0
        for wanted in wanted_artists:
            for found in found_artists:
                if wanted == found:
                    artist_score = max(artist_score, 40)
                elif contains_meaningful_text(wanted, found) or contains_meaningful_text(found, wanted):
                    artist_score = max(artist_score, 30)
                elif text_similarity(wanted, found) >= 0.88:
                    artist_score = max(artist_score, 25)

        if wanted_artists and found_artists and artist_score == 0:
            return 0
        return title_score + artist_score

    def find_qqmusic_art(self, title: str, artists: list[str]) -> str:
        best_score = 0
        best_album_mid = ""
        queries = self.qqmusic_queries(title, artists)
        for query in queries:
            try:
                response = self.session.get(
                    "https://c.y.qq.com/soso/fcgi-bin/client_search_cp",
                    params={
                        "format": "json",
                        "n": 12,
                        "p": 1,
                        "w": query,
                        "cr": 1,
                        "new_json": 1,
                        "remoteplace": "txt.mqq.all",
                    },
                    timeout=6,
                )
                response.raise_for_status()
                songs = response.json().get("data", {}).get("song", {}).get("list", [])
            except Exception as exc:
                logging.debug("qqmusic art search failed query=%r error=%s", query, exc)
                continue

            for song in songs:
                if not isinstance(song, dict):
                    continue
                album_mid = self.qqmusic_album_mid(song)
                if not album_mid:
                    continue
                score = self.qqmusic_song_score(song, title, artists)
                if score > best_score:
                    best_score = score
                    best_album_mid = album_mid

            if best_score >= 130:
                break

        min_score = 90 if not artists else 115
        if best_album_mid and best_score >= min_score:
            logging.debug("qqmusic art matched score=%s album_mid=%s title=%r", best_score, best_album_mid, title)
            return f"https://y.gtimg.cn/music/photo_new/T002R800x800M000{best_album_mid}.jpg"

        logging.debug("qqmusic art search had no confident match title=%r artist=%r", title, joined_artists(artists))
        return ""

    def find_itunes_art(self, title: str, artists: list[str]) -> str:
        artist = artists[0] if artists else ""
        stripped_title = re.sub(r"[\u4e00-\u9fff]+", "", title).strip()
        queries = unique_nonempty([f"{title} {artist}", title, f"{stripped_title} {artist}", stripped_title])
        countries = ["CN", "US", "JP"]

        for country in countries:
            for query in queries:
                try:
                    response = self.session.get(
                        "https://itunes.apple.com/search",
                        params={
                            "term": query,
                            "media": "music",
                            "entity": "song",
                            "limit": 5,
                            "country": country,
                        },
                        timeout=6,
                    )
                    response.raise_for_status()
                    results = response.json().get("results", [])
                except Exception as exc:
                    logging.debug("itunes art search failed query=%r country=%s error=%s", query, country, exc)
                    continue

                for item in results:
                    url = item.get("artworkUrl100", "")
                    if url:
                        return url.replace("100x100bb", "1000x1000bb").replace("100x100-999", "1000x1000-999")
        return ""

    def download_art_url(self, url: str) -> str:
        digest = hashlib.sha256(url.encode("utf-8", errors="ignore")).hexdigest()
        target = self.art_dir / f"{digest}.jpg"
        if target.exists() and target.stat().st_size > 0:
            self.record_art_access(url, target)
            return target.resolve().as_uri()

        tmp = target.with_suffix(".tmp")
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if content_type and "image" not in content_type:
                logging.debug("art url did not return an image url=%s content_type=%s", url, content_type)
                return ""
            if not response.content:
                return ""
            tmp.write_bytes(response.content)
            tmp.replace(target)
            self.record_art_access(url, target)
            return target.resolve().as_uri()
        except Exception as exc:
            logging.debug("art download failed url=%s error=%s", url, exc)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            return ""
