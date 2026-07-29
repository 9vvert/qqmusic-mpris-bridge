import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from dbus_next import BusType
from dbus_next.aio import MessageBus

from .art import AlbumArtResolver
from .constants import BRIDGE_BUS_NAME, MPRIS_PATH
from .metadata import TrackState
from .mpris import MprisPlayerInterface, MprisRootInterface, QQMusicMprisBridge


def parse_sources(raw: str) -> list[str]:
    allowed = {"qqmusic", "itunes"}
    sources: list[str] = []
    for item in raw.split(","):
        item = item.strip().lower()
        if item and item in allowed and item not in sources:
            sources.append(item)
    return sources or ["qqmusic"]


def state_to_jsonable(state: TrackState) -> dict[str, Any]:
    return {
        "source_bus": state.source_bus,
        "playback_status": state.playback_status,
        "title": state.title,
        "artists": state.artists,
        "album": state.album,
        "source_url": state.source_url,
        "original_art_url": state.original_art_url,
        "resolved_art_url": state.art_url,
        "can_control": state.can_control,
    }


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        logging.warning("ignoring invalid %s=%r", name, raw)
        return default


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logging.warning("ignoring invalid %s=%r", name, raw)
        return default


def default_fallback_interval() -> float:
    if "QQMUSIC_MPRIS_BRIDGE_FALLBACK_INTERVAL" in os.environ:
        return env_float("QQMUSIC_MPRIS_BRIDGE_FALLBACK_INTERVAL", 30.0)
    return env_float("QQMUSIC_MPRIS_BRIDGE_POLL_INTERVAL", 30.0)


async def async_main() -> int:
    parser = argparse.ArgumentParser(description="Publish QQMusic MPRIS metadata with resolved album art.")
    parser.add_argument("--once", action="store_true", help="print one resolved QQMusic state and exit")
    parser.add_argument("--debug", action="store_true", help="enable debug logging")
    parser.add_argument(
        "--fallback-interval",
        type=float,
        default=default_fallback_interval(),
        help="low-frequency fallback scan interval in seconds",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=None,
        help="deprecated alias for --fallback-interval",
    )
    parser.add_argument(
        "--debounce-ms",
        type=float,
        default=env_float("QQMUSIC_MPRIS_BRIDGE_DEBOUNCE_MS", 350.0),
        help="delay before refreshing after MPRIS events, in milliseconds",
    )
    parser.add_argument(
        "--art-sources",
        default=os.environ.get("QQMUSIC_MPRIS_BRIDGE_ART_SOURCES", "qqmusic"),
        help="comma-separated artwork sources: qqmusic,itunes; qqmusic is authoritative when listed",
    )
    parser.add_argument(
        "--max-art-cache-items",
        type=int,
        default=env_int("QQMUSIC_MPRIS_BRIDGE_MAX_ART_CACHE_ITEMS", 10),
        help="maximum number of local artwork files to keep",
    )
    parser.add_argument(
        "--no-noctalia-preference",
        action="store_true",
        help="do not ask Noctalia to pin this bridge as active media player",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    fallback_interval = args.poll_interval if args.poll_interval is not None else args.fallback_interval
    cache_dir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "qqmusic-mpris-bridge"
    resolver = AlbumArtResolver(
        cache_dir,
        parse_sources(args.art_sources),
        max_art_cache_items=args.max_art_cache_items,
    )
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    bridge = QQMusicMprisBridge(
        bus=bus,
        resolver=resolver,
        fallback_interval=max(5.0, fallback_interval),
        debounce_delay=max(0.05, args.debounce_ms / 1000),
        set_noctalia_preference=not args.no_noctalia_preference and not args.once,
    )

    if args.once:
        state = await bridge.update_once(emit=False)
        print(json.dumps(state_to_jsonable(state), ensure_ascii=False, indent=2))
        return 0 if state.has_track() else 1

    root_interface = MprisRootInterface()
    player_interface = MprisPlayerInterface(bridge)
    bridge.player_interface = player_interface
    bus.export(MPRIS_PATH, root_interface)
    bus.export(MPRIS_PATH, player_interface)
    await bus.request_name(BRIDGE_BUS_NAME)
    await bridge.run()
    return 0


def main() -> int:
    try:
        return asyncio.run(async_main())
    except KeyboardInterrupt:
        return 130
