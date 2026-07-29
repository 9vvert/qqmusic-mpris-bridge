# qqmusic-mpris-bridge

语言：[简体中文](README.md) | [English](README.en.md)

这是Linux版`qqmusic`的MPRIS封面补全服务。

linux qqmusic默认暴露的MPRIS metadata缺少封面字段，因此一些桌面环境的组件无法正确读取(比如`noctalia-shell`的media组件)

该工具会启动一个新的MPRIS player，读取 QQ 音乐原始 MPRIS metadata，再补全 `mpris:artUrl`，让支持MPRIS的桌面组件可以显示封面。

## Install
### General Linux

```sh
git clone git@github.com:9vvert/qqmusic-mpris-bridge.git
cd qqmusic-mpris-bridge
./install.sh
```

这会安装到当前的用户目录中：
```text
~/.local/lib/qqmusic-mpris-bridge/venv/
~/.local/bin/qqmusic-mpris-bridge
~/.config/systemd/user/qqmusic-mpris-bridge.service
```

查看服务状态：
```sh
systemctl --user status qqmusic-mpris-bridge.service
```

查看日志：
```sh
journalctl --user -u qqmusic-mpris-bridge.service -f
```

手动控制服务：
```sh
systemctl --user start qqmusic-mpris-bridge.service
systemctl --user restart qqmusic-mpris-bridge.service
systemctl --user stop qqmusic-mpris-bridge.service
systemctl --user enable qqmusic-mpris-bridge.service
systemctl --user disable qqmusic-mpris-bridge.service
```

卸载：
```sh
./uninstall.sh --remove-cache
```

### NixOS Home Manager 

这个仓库导出了 flake package 和 Home Manager module。你可以直接在自己的 flake 中引用。

在你的 `flake.nix` 中添加 input：

```nix
{
  inputs.qqmusic-mpris-bridge = {
    url = "github:9vvert/qqmusic-mpris-bridge";
    inputs.nixpkgs.follows = "nixpkgs";
  };
}
```

如果你的 `outputs` 已经写成这样：

```nix
outputs = { self, nixpkgs, home-manager, ... } @ inputs: {
  # ...
};
```

那么 Home Manager 配置中可以直接使用 `inputs`。

在你的 Home Manager module 中导入：

```nix
{ inputs, ... }:
{
  imports = [
    inputs.qqmusic-mpris-bridge.homeModules.default
  ];
}
```

启用服务：

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

也可以直接测试 flake package：

```sh
nix run github:9vvert/qqmusic-mpris-bridge -- --once --debug
```

或构建：

```sh
nix build github:9vvert/qqmusic-mpris-bridge
```

#### Home Manager参数

- `services.qqmusic-mpris-bridge.enable`

Type：`bool`
Default：`false`
Description：是否启用 Home Manager 管理的用户级 systemd 服务。

- `services.qqmusic-mpris-bridge.package`

Type：`package`
Default：当前 flake 构建出的 `qqmusic-mpris-bridge` package。
Description：通常不需要修改。你可以用它覆盖成自己打包的版本。

- `services.qqmusic-mpris-bridge.fallbackInterval`

Type：`number`
Default：`30`
Description：是否启用低频兜底扫描间隔(单位秒)。正常情况下歌曲切换依靠 D-Bus 事件监听，并不需要设置该参数进行轮询.

- `services.qqmusic-mpris-bridge.debounceMs`

Type：`number`
Default：`350`
Description：收到 MPRIS 事件后延迟刷新的时间，单位毫秒。QQ 音乐切歌时可能连续发出多次不完整metadata，适当 debounce 可以避免读到中间状态。

- `services.qqmusic-mpris-bridge.maxArtCacheItems`

Type：`number` (Positive)
Default：`10`
Description：本地最多保留多少张封面缓存。服务会用一个 manifest 文件记录最近访问时间，并按
LRU 方式删除最久未使用的封面。

- `services.qqmusic-mpris-bridge.noctaliaPreference`

Type：`bool`
Default：`true`
Description：是否请求 Noctalia 优先使用这个 bridge player。

如果你不用 Noctalia，或者不希望它自动选择这个 player，可以设置：

```nix
services.qqmusic-mpris-bridge.noctaliaPreference = false;
```

## 在组件中使用该MPRIS源
该工具会额外暴露一个 MPRIS player：

```text
org.mpris.MediaPlayer2.qqmusic_art_bridge
```

在一些工具中，player 名称会省略 `org.mpris.MediaPlayer2.` 前缀，因此也可能显示为：

```text
qqmusic_art_bridge
```

可以先用 `playerctl` 确认服务是否已经被桌面 session 识别：

```sh
playerctl -l
playerctl -p qqmusic_art_bridge metadata
```

如果输出中能看到 `mpris:artUrl`，说明 bridge 已经正常提供封面。后续桌面组件只需要
选择这个 MPRIS player，而不是 QQ 音乐原始的 Chromium/Electron MPRIS player。

### noctalia shell

如果使用 Noctalia，可以直接通过 Home Manager 参数让本服务请求 Noctalia 优先使用
这个 bridge player：

```nix
services.qqmusic-mpris-bridge.noctaliaPreference = true;
```

这是默认值。它会调用 Noctalia 的私有 D-Bus 接口，请求 Noctalia 将当前媒体源切到 `org.mpris.MediaPlayer2.qqmusic_art_bridge`

如果你不用 Noctalia，或者不希望服务主动修改 Noctalia 的当前媒体源，则关闭该选项：

```nix
services.qqmusic-mpris-bridge.noctaliaPreference = false;
```

### other quickshell

其他基于 Quickshell 的组件不会使用 Noctalia 的私有偏好接口，因此需要在组件配置
中手动选择这个 MPRIS player。

如果组件提供 preferred player / player name / MPRIS source 之类的配置，优先尝试：

```text
qqmusic_art_bridge
```

如果它要求完整 D-Bus 名称，则填写：

```text
org.mpris.MediaPlayer2.qqmusic_art_bridge
```

如果是自己编写的 Quickshell QML，可以按 `dbusName` 过滤：

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

## 缓存

封面缓存目录：
```text
${XDG_CACHE_HOME:-~/.cache}/qqmusic-mpris-bridge/art
```
缓存 manifest：
```text
${XDG_CACHE_HOME:-~/.cache}/qqmusic-mpris-bridge/art-cache.json
```

缓存文件名是封面 URL 的 SHA-256。再次遇到同一封面时会复用本地文件并更新
LRU 访问时间。默认最多保留 10 张封面，可以通过命令行或 Home Manager 的
`maxArtCacheItems` 修改。

## 注意事项
- 请勿同时用 `install.sh` 和 Home Manager 管理同一个`qqmusic-mpris-bridge.service`。

- QQ 音乐原始 MPRIS 信息很有限，缺少 album、url、length、artUrl 时只能用title/artist 搜索；该工具会尽量避免错误匹配，但不能保证100%正确。
