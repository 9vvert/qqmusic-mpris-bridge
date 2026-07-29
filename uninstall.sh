#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./uninstall.sh [options]

Remove the current user's qqmusic-mpris-bridge installation.

Options:
  --prefix PATH     Remove installation under PATH instead of ~/.local
  --remove-cache    Also remove ~/.cache/qqmusic-mpris-bridge
  -h, --help        Show this help
EOF
}

info() {
  printf '%s\n' "$*"
}

prefix="${PREFIX:-$HOME/.local}"
remove_cache=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix)
      [[ $# -ge 2 ]] || { printf 'error: --prefix requires a path\n' >&2; exit 1; }
      prefix="$2"
      shift 2
      ;;
    --remove-cache)
      remove_cache=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'error: unknown option: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

lib_dir="${QQMUSIC_MPRIS_BRIDGE_LIB_DIR:-$prefix/lib/qqmusic-mpris-bridge}"
bin_dir="${QQMUSIC_MPRIS_BRIDGE_BIN_DIR:-$prefix/bin}"
bin_link="$bin_dir/qqmusic-mpris-bridge"
systemd_user_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
service_file="$systemd_user_dir/qqmusic-mpris-bridge.service"
cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/qqmusic-mpris-bridge"

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user disable --now qqmusic-mpris-bridge.service >/dev/null 2>&1 || true
fi

rm -f "$service_file"
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload >/dev/null 2>&1 || true
fi

if [[ -L "$bin_link" ]]; then
  rm -f "$bin_link"
elif [[ -e "$bin_link" ]]; then
  info "Not removing non-symlink command path: $bin_link"
fi

rm -rf "$lib_dir"

if [[ "$remove_cache" -eq 1 ]]; then
  rm -rf "$cache_dir"
fi

info "Removed qqmusic-mpris-bridge user installation."

