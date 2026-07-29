import asyncio
import logging
from pathlib import Path
from typing import Any

from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus
from dbus_next.service import PropertyAccess, ServiceInterface, dbus_property, method, signal

from .art import AlbumArtResolver
from .constants import (
    BRIDGE_BUS_NAME,
    DBUS_DEST,
    DBUS_IFACE,
    DBUS_PATH,
    MPRIS_PATH,
    MPRIS_PREFIX,
    NOCTALIA_MPRIS_DEST,
    NOCTALIA_MPRIS_IFACE,
    NOCTALIA_MPRIS_PATH,
    PLAYER_IFACE,
    PROPS_IFACE,
    ROOT_IFACE,
    VALID_PLAYBACK_STATUS,
)
from .metadata import (
    TrackState,
    artists_from_metadata,
    as_bool,
    as_float,
    as_int,
    as_string,
    joined_artists,
    metadata_value,
    unwrap,
)


class MprisRootInterface(ServiceInterface):
    def __init__(self) -> None:
        super().__init__(ROOT_IFACE)

    @method()
    def Raise(self) -> None:
        return None

    @method()
    def Quit(self) -> None:
        return None

    @dbus_property(access=PropertyAccess.READWRITE)
    def Fullscreen(self) -> "b":
        return False

    @Fullscreen.setter
    def Fullscreen(self, value: "b") -> None:
        return None

    @dbus_property(access=PropertyAccess.READ)
    def CanQuit(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def CanRaise(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def CanSetFullscreen(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def HasTrackList(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def Identity(self) -> "s":
        return "QQMusic"

    @dbus_property(access=PropertyAccess.READ)
    def DesktopEntry(self) -> "s":
        return "qqmusic"

    @dbus_property(access=PropertyAccess.READ)
    def SupportedUriSchemes(self) -> "as":
        return []

    @dbus_property(access=PropertyAccess.READ)
    def SupportedMimeTypes(self) -> "as":
        return []


class MprisPlayerInterface(ServiceInterface):
    def __init__(self, bridge: "QQMusicMprisBridge") -> None:
        super().__init__(PLAYER_IFACE)
        self.bridge = bridge

    @method()
    def Next(self) -> None:
        self.bridge.call_source_method_later("Next")

    @method()
    def Previous(self) -> None:
        self.bridge.call_source_method_later("Previous")

    @method()
    def Pause(self) -> None:
        self.bridge.call_source_method_later("Pause")

    @method()
    def PlayPause(self) -> None:
        self.bridge.call_source_method_later("PlayPause")

    @method()
    def Stop(self) -> None:
        self.bridge.call_source_method_later("Stop")

    @method()
    def Play(self) -> None:
        self.bridge.call_source_method_later("Play")

    @method()
    def Seek(self, Offset: "x") -> None:
        self.bridge.call_source_method_later("Seek", "x", [Offset])

    @method()
    def SetPosition(self, TrackId: "o", Position: "x") -> None:
        self.bridge.call_source_method_later("SetPosition", "ox", [TrackId, Position])

    @method()
    def OpenUri(self, Uri: "s") -> None:
        self.bridge.call_source_method_later("OpenUri", "s", [Uri])

    @signal()
    def Seeked(self, Position: "x") -> "x":
        return Position

    @dbus_property(access=PropertyAccess.READ)
    def PlaybackStatus(self) -> "s":
        return self.bridge.state.playback_status

    @dbus_property(access=PropertyAccess.READWRITE)
    def LoopStatus(self) -> "s":
        return self.bridge.state.loop_status

    @LoopStatus.setter
    def LoopStatus(self, value: "s") -> None:
        self.bridge.set_source_property_later("LoopStatus", "s", value)

    @dbus_property(access=PropertyAccess.READWRITE)
    def Rate(self) -> "d":
        return 1.0

    @Rate.setter
    def Rate(self, value: "d") -> None:
        return None

    @dbus_property(access=PropertyAccess.READWRITE)
    def Shuffle(self) -> "b":
        return self.bridge.state.shuffle

    @Shuffle.setter
    def Shuffle(self, value: "b") -> None:
        self.bridge.set_source_property_later("Shuffle", "b", value)

    @dbus_property(access=PropertyAccess.READ)
    def Metadata(self) -> "a{sv}":
        return self.bridge.state.metadata()

    @dbus_property(access=PropertyAccess.READWRITE)
    def Volume(self) -> "d":
        return self.bridge.state.volume

    @Volume.setter
    def Volume(self, value: "d") -> None:
        self.bridge.set_source_property_later("Volume", "d", value)

    @dbus_property(access=PropertyAccess.READ)
    def Position(self) -> "x":
        return self.bridge.state.position_us

    @dbus_property(access=PropertyAccess.READ)
    def MinimumRate(self) -> "d":
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def MaximumRate(self) -> "d":
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def CanGoNext(self) -> "b":
        return self.bridge.state.can_go_next

    @dbus_property(access=PropertyAccess.READ)
    def CanGoPrevious(self) -> "b":
        return self.bridge.state.can_go_previous

    @dbus_property(access=PropertyAccess.READ)
    def CanPlay(self) -> "b":
        return self.bridge.state.can_play

    @dbus_property(access=PropertyAccess.READ)
    def CanPause(self) -> "b":
        return self.bridge.state.can_pause

    @dbus_property(access=PropertyAccess.READ)
    def CanSeek(self) -> "b":
        return self.bridge.state.can_seek

    @dbus_property(access=PropertyAccess.READ)
    def CanControl(self) -> "b":
        return self.bridge.state.can_control

    def emit_track_properties_changed(self) -> None:
        self.emit_properties_changed(
            {
                "PlaybackStatus": self.PlaybackStatus,
                "LoopStatus": self.LoopStatus,
                "Shuffle": self.Shuffle,
                "Metadata": self.Metadata,
                "Volume": self.Volume,
                "CanGoNext": self.CanGoNext,
                "CanGoPrevious": self.CanGoPrevious,
                "CanPlay": self.CanPlay,
                "CanPause": self.CanPause,
                "CanSeek": self.CanSeek,
                "CanControl": self.CanControl,
            }
        )


class QQMusicMprisBridge:
    def __init__(
        self,
        bus: MessageBus,
        resolver: AlbumArtResolver,
        fallback_interval: float,
        debounce_delay: float,
        set_noctalia_preference: bool,
    ) -> None:
        self.bus = bus
        self.resolver = resolver
        self.fallback_interval = fallback_interval
        self.debounce_delay = debounce_delay
        self.set_noctalia_preference = set_noctalia_preference
        self.state = TrackState()
        self.player_interface: MprisPlayerInterface | None = None
        self.last_change_key: tuple[Any, ...] | None = None
        self.last_logged_track: tuple[str, str] | None = None
        self.preference_requested = False
        self.update_lock = asyncio.Lock()
        self.debounce_task: asyncio.Task[None] | None = None

    async def dbus_call(
        self,
        destination: str,
        path: str,
        interface: str,
        member: str,
        signature: str = "",
        body: list[Any] | None = None,
    ) -> list[Any]:
        reply = await self.bus.call(
            Message(
                destination=destination,
                path=path,
                interface=interface,
                member=member,
                signature=signature,
                body=body or [],
            )
        )
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(f"{reply.error_name}: {reply.body}")
        return reply.body

    async def list_names(self) -> list[str]:
        body = await self.dbus_call(DBUS_DEST, DBUS_PATH, DBUS_IFACE, "ListNames")
        return list(body[0])

    async def get_connection_pid(self, bus_name: str) -> int:
        body = await self.dbus_call(
            DBUS_DEST,
            DBUS_PATH,
            DBUS_IFACE,
            "GetConnectionUnixProcessID",
            "s",
            [bus_name],
        )
        return int(body[0])

    async def get_all(self, bus_name: str, interface: str) -> dict[str, Variant]:
        body = await self.dbus_call(
            bus_name,
            MPRIS_PATH,
            PROPS_IFACE,
            "GetAll",
            "s",
            [interface],
        )
        return dict(body[0])

    async def is_qqmusic_bus(self, bus_name: str) -> bool:
        try:
            pid = await self.get_connection_pid(bus_name)
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ")
            decoded = cmdline.decode("utf-8", errors="ignore").casefold()
            return "qqmusic" in decoded
        except Exception as exc:
            logging.debug("failed to inspect owner pid for %s: %s", bus_name, exc)
            return False

    async def read_source_state(self) -> TrackState:
        states: list[TrackState] = []
        for bus_name in await self.list_names():
            if not bus_name.startswith(MPRIS_PREFIX) or bus_name == BRIDGE_BUS_NAME:
                continue
            if not await self.is_qqmusic_bus(bus_name):
                continue
            try:
                root_props = await self.get_all(bus_name, ROOT_IFACE)
                player_props = await self.get_all(bus_name, PLAYER_IFACE)
            except Exception as exc:
                logging.debug("failed to read mpris props from %s: %s", bus_name, exc)
                continue

            metadata = unwrap(player_props.get("Metadata"), {})
            if not isinstance(metadata, dict):
                metadata = {}

            playback_status = as_string(player_props.get("PlaybackStatus"), "Stopped")
            if playback_status not in VALID_PLAYBACK_STATUS:
                playback_status = "Stopped"

            title = as_string(metadata_value(metadata, "xesam:title"), "")
            artists = artists_from_metadata(metadata)
            album = as_string(metadata_value(metadata, "xesam:album"), "")
            state = TrackState(
                source_bus=bus_name,
                playback_status=playback_status,
                title=title,
                artists=artists,
                album=album,
                source_url=as_string(metadata_value(metadata, "xesam:url"), ""),
                original_art_url=as_string(metadata_value(metadata, "mpris:artUrl"), ""),
                position_us=as_int(player_props.get("Position"), 0),
                length_us=as_int(metadata_value(metadata, "mpris:length"), 0),
                loop_status=as_string(player_props.get("LoopStatus"), "None"),
                shuffle=as_bool(player_props.get("Shuffle"), False),
                volume=as_float(player_props.get("Volume"), 1.0),
                can_control=as_bool(player_props.get("CanControl"), True),
                can_play=as_bool(player_props.get("CanPlay"), True),
                can_pause=as_bool(player_props.get("CanPause"), True),
                can_go_next=as_bool(player_props.get("CanGoNext"), True),
                can_go_previous=as_bool(player_props.get("CanGoPrevious"), True),
                can_seek=as_bool(player_props.get("CanSeek"), False),
            )
            identity = as_string(root_props.get("Identity"), "")
            logging.debug("candidate %s identity=%r title=%r status=%s", bus_name, identity, title, playback_status)
            states.append(state)

        if not states:
            return TrackState()

        states.sort(key=lambda s: (s.playback_status == "Playing", s.has_track()), reverse=True)
        return states[0]

    async def update_once(self, emit: bool = True) -> TrackState:
        new_state = await self.read_source_state()
        if new_state.has_track():
            new_state.art_url = await self.resolver.resolve(new_state)

        changed = new_state.change_key() != self.last_change_key
        self.state = new_state
        self.last_change_key = new_state.change_key()

        if changed:
            track_key = (self.state.title, joined_artists(self.state.artists))
            if self.state.has_track() and track_key != self.last_logged_track:
                logging.info(
                    "track source=%s status=%s title=%r artist=%r art=%s",
                    self.state.source_bus,
                    self.state.playback_status,
                    self.state.title,
                    joined_artists(self.state.artists),
                    self.state.art_url or "<none>",
                )
                self.last_logged_track = track_key
            elif not self.state.has_track() and self.last_logged_track is not None:
                logging.info("no qqmusic track found")
                self.last_logged_track = None

            if emit and self.player_interface is not None:
                self.player_interface.emit_track_properties_changed()

        if self.state.has_track() and self.set_noctalia_preference and (changed or not self.preference_requested):
            await self.request_noctalia_preference()
        elif not self.state.has_track():
            self.preference_requested = False

        return self.state

    async def request_noctalia_preference(self) -> None:
        try:
            await self.dbus_call(
                NOCTALIA_MPRIS_DEST,
                NOCTALIA_MPRIS_PATH,
                NOCTALIA_MPRIS_IFACE,
                "SetActivePlayerPreference",
                "s",
                [BRIDGE_BUS_NAME],
            )
            if not self.preference_requested:
                logging.info("requested Noctalia active player preference for %s", BRIDGE_BUS_NAME)
            self.preference_requested = True
        except Exception as exc:
            logging.debug("failed to set Noctalia active player preference: %s", exc)

    def call_source_method_later(self, member: str, signature: str = "", body: list[Any] | None = None) -> None:
        if not self.state.source_bus:
            return
        asyncio.create_task(self.call_source_method(member, signature, body or []))

    async def call_source_method(self, member: str, signature: str = "", body: list[Any] | None = None) -> None:
        try:
            await self.dbus_call(self.state.source_bus, MPRIS_PATH, PLAYER_IFACE, member, signature, body or [])
        except Exception as exc:
            logging.debug("failed to forward %s to %s: %s", member, self.state.source_bus, exc)

    def set_source_property_later(self, prop: str, signature: str, value: Any) -> None:
        if not self.state.source_bus:
            return
        asyncio.create_task(self.set_source_property(prop, signature, value))

    async def set_source_property(self, prop: str, signature: str, value: Any) -> None:
        try:
            await self.dbus_call(
                self.state.source_bus,
                MPRIS_PATH,
                PROPS_IFACE,
                "Set",
                "ssv",
                [PLAYER_IFACE, prop, Variant(signature, value)],
            )
        except Exception as exc:
            logging.debug("failed to forward property %s to %s: %s", prop, self.state.source_bus, exc)

    async def add_signal_match(self, match_rule: str) -> None:
        await self.dbus_call(
            DBUS_DEST,
            DBUS_PATH,
            DBUS_IFACE,
            "AddMatch",
            "s",
            [match_rule],
        )

    async def install_signal_matches(self) -> None:
        match_rules = [
            (
                "type='signal',interface='org.freedesktop.DBus.Properties',"
                "member='PropertiesChanged',path='/org/mpris/MediaPlayer2'"
            ),
            (
                "type='signal',sender='org.freedesktop.DBus',interface='org.freedesktop.DBus',"
                "member='NameOwnerChanged',path='/org/freedesktop/DBus'"
            ),
        ]
        for match_rule in match_rules:
            try:
                await self.add_signal_match(match_rule)
            except Exception as exc:
                logging.warning("failed to add D-Bus match rule %r: %s", match_rule, exc)

    def handle_dbus_message(self, message: Message) -> None:
        if message.message_type != MessageType.SIGNAL:
            return None
        if message.sender == getattr(self.bus, "unique_name", None):
            return None

        if (
            message.path == MPRIS_PATH
            and message.interface == PROPS_IFACE
            and message.member == "PropertiesChanged"
            and message.body
            and message.body[0] == PLAYER_IFACE
        ):
            changed = message.body[1] if len(message.body) > 1 and isinstance(message.body[1], dict) else {}
            interesting = {
                "Metadata",
                "PlaybackStatus",
                "LoopStatus",
                "Shuffle",
                "Volume",
                "CanControl",
                "CanPlay",
                "CanPause",
                "CanGoNext",
                "CanGoPrevious",
                "CanSeek",
            }
            if not changed or interesting.intersection(changed.keys()):
                self.schedule_update("mpris-properties")
            return None

        if (
            message.path == DBUS_PATH
            and message.interface == DBUS_IFACE
            and message.member == "NameOwnerChanged"
            and len(message.body) >= 3
        ):
            name = str(message.body[0])
            if name.startswith(MPRIS_PREFIX) and name != BRIDGE_BUS_NAME:
                self.schedule_update("mpris-name-owner")
            return None

        return None

    def schedule_update(self, reason: str) -> None:
        if self.debounce_task is not None and not self.debounce_task.done():
            self.debounce_task.cancel()
        self.debounce_task = asyncio.create_task(self.debounced_update(reason))

    async def debounced_update(self, reason: str) -> None:
        try:
            await asyncio.sleep(self.debounce_delay)
            await self.safe_update(reason)
        except asyncio.CancelledError:
            pass

    async def safe_update(self, reason: str) -> None:
        async with self.update_lock:
            try:
                logging.debug("refreshing state reason=%s", reason)
                await self.update_once()
            except Exception as exc:
                logging.warning("bridge update failed reason=%s error=%s", reason, exc)

    async def run(self) -> None:
        logging.info(
            "qqmusic mpris bridge started fallback_interval=%.1fs debounce=%.0fms",
            self.fallback_interval,
            self.debounce_delay * 1000,
        )
        self.bus.add_message_handler(self.handle_dbus_message)
        await self.install_signal_matches()
        await self.safe_update("startup")
        while True:
            await asyncio.sleep(self.fallback_interval)
            await self.safe_update("fallback")

