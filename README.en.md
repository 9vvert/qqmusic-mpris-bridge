# qqmusic-mpris-bridge

Language: [简体中文](README.md) | [English](README.en.md)

This is an MPRIS album-art completion service for the Linux version of `qqmusic`.

The Linux version of QQMusic exposes MPRIS metadata without album art in many cases, so some desktop components cannot read it correctly, such as the media component in `noctalia-shell`.

This tool starts a new MPRIS player, reads the original QQMusic MPRIS metadata, fills in `mpris:artUrl`, and lets MPRIS-compatible desktop components display album art.

## Install
### General Linux

```sh
git clone git@github.com:9vvert/qqmusic-mpris-bridge.git
cd qqmusic-mpris-bridge
./install.sh
```

This installs into the current user's directories:
```text
~/.local/lib/qqmusic-mpris-bridge/venv/
~/.local/bin/qqmusic-mpris-bridge
~/.config/systemd/user/qqmusic-mpris-bridge.service
```

Check service status:
```sh
systemctl --user status qqmusic-mpris-bridge.service
```

View logs:
```sh
journalctl --user -u qqmusic-mpris-bridge.service -f
```

Control the service manually:
```sh
systemctl --user start qqmusic-mpris-bridge.service
systemctl --user restart qqmusic-mpris-bridge.service
systemctl --user stop qqmusic-mpris-bridge.service
systemctl --user enable qqmusic-mpris-bridge.service
systemctl --user disable qqmusic-mpris-bridge.service
```

Uninstall:
```sh
./uninstall.sh --remove-cache
```

### NixOS Home Manager 

This repository exports a flake package and a Home Manager module. You can reference it directly from your own flake.

Add this input to your `flake.nix`:

```nix
{
  inputs.qqmusic-mpris-bridge = {
    url = "github:9vvert/qqmusic-mpris-bridge";
    inputs.nixpkgs.follows = "nixpkgs";
  };
}
```

If your `outputs` are already written like this:

```nix
outputs = { self, nixpkgs, home-manager, ... } @ inputs: {
  # ...
};
```

then `inputs` can be used directly in your Home Manager configuration.

Import the module in your Home Manager module:

```nix
{ inputs, ... }:
{
  imports = [
    inputs.qqmusic-mpris-bridge.homeModules.default
  ];
}
```

Enable the service:

```nix
{
  services.qqmusic-mpris-bridge = {
    enable = true;
    artSources = [ "qqmusic" ];
    fallbackInterval = 30;
    debounceMs = 350;
    maxArtCacheItems = 10;
    noctaliaPreference = true;
  };
}
```

You can also test the flake package directly:

```sh
nix run github:9vvert/qqmusic-mpris-bridge -- --once --debug
```

Or build it:

```sh
nix build github:9vvert/qqmusic-mpris-bridge
```

#### Home Manager Options

- `services.qqmusic-mpris-bridge.enable`

Type: `bool`

Default: `false`

Description: Whether to enable the user-level systemd service managed by Home Manager.

- `services.qqmusic-mpris-bridge.package`

Type: `package`

Default: The `qqmusic-mpris-bridge` package built by this flake.

Description: Usually does not need to be changed. You can override it with your own package.

- `services.qqmusic-mpris-bridge.fallbackInterval`

Type: `number`

Default: `30`

Description: Whether to enable the low-frequency fallback scan interval, in seconds. Normally track changes are handled through D-Bus event listening, so this does not need to be set for polling.

- `services.qqmusic-mpris-bridge.debounceMs`

Type: `number`

Default: `350`

Description: Delay before refreshing after MPRIS events, in milliseconds. QQMusic may emit multiple incomplete metadata updates during track changes, and a suitable debounce can avoid reading an intermediate state.

- `services.qqmusic-mpris-bridge.maxArtCacheItems`

Type: `number` (Positive)

Default: `10`

Description: Maximum number of local album-art cache files to keep. The service records recent access time in a manifest file and removes the least recently used artwork by LRU.

- `services.qqmusic-mpris-bridge.noctaliaPreference`

Type: `bool`

Default: `true`

Description: Whether to ask Noctalia to prefer this bridge player.

If you do not use Noctalia, or do not want it to automatically choose this player, set:

```nix
services.qqmusic-mpris-bridge.noctaliaPreference = false;
```

## Using This MPRIS Source In Components
This tool exposes an additional MPRIS player:

```text
org.mpris.MediaPlayer2.qqmusic_art_bridge
```

In some tools, the player name omits the `org.mpris.MediaPlayer2.` prefix, so it may also appear as:

```text
qqmusic_art_bridge
```

You can first use `playerctl` to confirm whether the service has been recognized by the desktop session:

```sh
playerctl -l
playerctl -p qqmusic_art_bridge metadata
```

If the output contains `mpris:artUrl`, the bridge is providing album art correctly. Desktop components only need to select this MPRIS player instead of QQMusic's original Chromium/Electron MPRIS player.

### noctalia shell

If you use Noctalia, the Home Manager option can make this service ask Noctalia to prefer this bridge player:

```nix
services.qqmusic-mpris-bridge.noctaliaPreference = true;
```

This is the default. It calls Noctalia's private D-Bus interface and asks Noctalia to switch the current media source to `org.mpris.MediaPlayer2.qqmusic_art_bridge`.

If you do not use Noctalia, or do not want the service to actively change Noctalia's current media source, disable this option:

```nix
services.qqmusic-mpris-bridge.noctaliaPreference = false;
```

### other quickshell

Other Quickshell-based components do not use Noctalia's private preference interface, so you need to manually select this MPRIS player in the component configuration.

If the component provides a preferred player, player name, or MPRIS source setting, try this first:

```text
qqmusic_art_bridge
```

If it requires the full D-Bus name, use:

```text
org.mpris.MediaPlayer2.qqmusic_art_bridge
```

If you write your own Quickshell QML, filter by `dbusName`:

```qml
import Quickshell
import Quickshell.Services.Mpris

Scope {
  readonly property string qqmusicBridgeBus: "org.mpris.MediaPlayer2.qqmusic_art_bridge"

  readonly property var qqmusicPlayer: Mpris.players.values.find(
    player => player.dbusName === qqmusicBridgeBus
  )

  readonly property string title: qqmusicPlayer ? qqmusicPlayer.trackTitle : ""
  readonly property string artist: qqmusicPlayer ? qqmusicPlayer.trackArtist : ""
  readonly property string artUrl: qqmusicPlayer ? qqmusicPlayer.trackArtUrl : ""
}
```

## Cache

Album-art cache directory:
```text
${XDG_CACHE_HOME:-~/.cache}/qqmusic-mpris-bridge/art
```
Cache manifest:
```text
${XDG_CACHE_HOME:-~/.cache}/qqmusic-mpris-bridge/art-cache.json
```

The cache filename is the SHA-256 hash of the album-art URL. When the same album art appears again, the local file is reused and the LRU access time is updated. By default, up to 10 album-art files are kept. This can be changed with the command line or Home Manager's `maxArtCacheItems`.

## Notes
- Do not manage the same `qqmusic-mpris-bridge.service` with both `install.sh` and Home Manager.
- The original QQMusic MPRIS data is very limited. When album, url, length, and artUrl are missing, the tool can only search by title/artist. This tool tries to avoid incorrect matches, but it cannot guarantee 100% correctness.
