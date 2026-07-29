# Linux版本QQ音乐封面抓取服务 

## Generic Linux Install

This installs for the current user only. It creates a Python virtual environment,
links the command into `~/.local/bin`, and installs a systemd user service under
`~/.config/systemd/user`.

The installer uses `pip` inside that virtual environment, so it needs access to
PyPI or an equivalent configured package index.

```sh
./install.sh
```

Useful options:

```sh
./install.sh --no-start
./install.sh --no-enable
./install.sh --no-service
./install.sh --prefix "$HOME/.local"
```

Check the service:

```sh
systemctl --user status qqmusic-mpris-bridge.service
journalctl --user -u qqmusic-mpris-bridge.service -f
```

Run once without installing the service:

```sh
qqmusic-mpris-bridge --once --debug
```

Uninstall:

```sh
./uninstall.sh
```

Remove cached artwork too:

```sh
./uninstall.sh --remove-cache
```

## Nix Flake
Use the Home Manager module from another flake:

```nix
{
  inputs.qqmusic-mpris-bridge.url = "path:/home/woc/repo/qqmusic-mpris-bridge";
}
```

Then add the module to your Home Manager imports:

```nix
{ inputs, ... }:
{
  imports = [
    inputs.qqmusic-mpris-bridge.homeModules.default
  ];

  services.qqmusic-mpris-bridge = {
    enable = true;
    artSources = [ "qqmusic" ];
    fallbackInterval = 30;
    debounceMs = 350;
    noctaliaPreference = true;
  };
}
```

## Notes

Do not enable both this user-installed service and a Home Manager/NixOS-managed
service with the same unit name at the same time. Pick one owner for
`qqmusic-mpris-bridge.service`.
