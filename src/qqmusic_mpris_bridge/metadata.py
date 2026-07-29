import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dbus_next import Variant

from .constants import NO_TRACK


def unwrap(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, Variant):
        return value.value
    return value


def metadata_value(metadata: dict[str, Any], key: str, default: Any = None) -> Any:
    return unwrap(metadata.get(key), default)


def as_string(value: Any, default: str = "") -> str:
    value = unwrap(value, default)
    if value is None:
        return default
    return str(value)


def as_bool(value: Any, default: bool = False) -> bool:
    value = unwrap(value, default)
    if value is None:
        return default
    return bool(value)


def as_int(value: Any, default: int = 0) -> int:
    value = unwrap(value, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 1.0) -> float:
    value = unwrap(value, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def artists_from_metadata(metadata: dict[str, Any]) -> list[str]:
    artists = metadata_value(metadata, "xesam:artist", [])
    if isinstance(artists, str):
        return [artists] if artists else []
    if isinstance(artists, (list, tuple)):
        return [str(artist) for artist in artists if str(artist)]
    return []


def joined_artists(artists: list[str]) -> str:
    return ", ".join(artist for artist in artists if artist)


def is_remote_url(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def is_file_url(value: str) -> bool:
    return value.lower().startswith("file://")


def local_art_url(value: str) -> str:
    if not value:
        return ""
    if is_file_url(value) or is_remote_url(value):
        return value
    if value.startswith("/"):
        return Path(value).expanduser().resolve().as_uri()
    return ""


def track_id_for(title: str, artists: list[str], album: str) -> str:
    if not title:
        return NO_TRACK
    raw = "\0".join([title, joined_artists(artists), album])
    digest = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()
    return f"/org/mpris/MediaPlayer2/Track/t{digest}"


@dataclass(eq=True)
class TrackState:
    source_bus: str = ""
    playback_status: str = "Stopped"
    title: str = ""
    artists: list[str] = field(default_factory=list)
    album: str = ""
    source_url: str = ""
    original_art_url: str = ""
    art_url: str = ""
    position_us: int = 0
    length_us: int = 0
    loop_status: str = "None"
    shuffle: bool = False
    volume: float = 1.0
    can_control: bool = False
    can_play: bool = False
    can_pause: bool = False
    can_go_next: bool = False
    can_go_previous: bool = False
    can_seek: bool = False

    def has_track(self) -> bool:
        return bool(self.title)

    def change_key(self) -> tuple[Any, ...]:
        return (
            self.source_bus,
            self.playback_status,
            self.title,
            tuple(self.artists),
            self.album,
            self.source_url,
            self.original_art_url,
            self.art_url,
            self.length_us,
            self.loop_status,
            self.shuffle,
            round(self.volume, 3),
            self.can_control,
            self.can_play,
            self.can_pause,
            self.can_go_next,
            self.can_go_previous,
            self.can_seek,
        )

    def metadata(self) -> dict[str, Variant]:
        if not self.has_track():
            return {"mpris:trackid": Variant("o", NO_TRACK)}

        result: dict[str, Variant] = {
            "mpris:trackid": Variant("o", track_id_for(self.title, self.artists, self.album)),
            "xesam:title": Variant("s", self.title),
            "xesam:artist": Variant("as", self.artists),
        }
        if self.album:
            result["xesam:album"] = Variant("s", self.album)
        if self.length_us > 0:
            result["mpris:length"] = Variant("x", self.length_us)
        if self.source_url:
            result["xesam:url"] = Variant("s", self.source_url)
        if self.art_url:
            result["mpris:artUrl"] = Variant("s", self.art_url)
        return result

