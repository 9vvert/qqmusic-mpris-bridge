#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

Install qqmusic-mpris-bridge for the current user.

Options:
  --prefix PATH   Install under PATH instead of ~/.local
  --no-service    Install only the command, skip systemd user service
  --no-enable     Install the service file but do not enable or start it
  --no-start      Enable the service but do not start/restart it now
  -h, --help      Show this help

Environment:
  QQMUSIC_MPRIS_BRIDGE_LIB_DIR   Override venv directory
  QQMUSIC_MPRIS_BRIDGE_BIN_DIR   Override command symlink directory
  XDG_CONFIG_HOME                Controls systemd user unit directory
EOF
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

info() {
  printf '%s\n' "$*"
}

prefix="${PREFIX:-$HOME/.local}"
install_service=1
enable_service=1
start_service=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix)
      [[ $# -ge 2 ]] || die "--prefix requires a path"
      prefix="$2"
      shift 2
      ;;
    --no-service)
      install_service=0
      enable_service=0
      start_service=0
      shift
      ;;
    --no-enable)
      enable_service=0
      start_service=0
      shift
      ;;
    --no-start)
      start_service=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
lib_dir="${QQMUSIC_MPRIS_BRIDGE_LIB_DIR:-$prefix/lib/qqmusic-mpris-bridge}"
bin_dir="${QQMUSIC_MPRIS_BRIDGE_BIN_DIR:-$prefix/bin}"
venv_dir="$lib_dir/venv"
command_path="$venv_dir/bin/qqmusic-mpris-bridge"
bin_link="$bin_dir/qqmusic-mpris-bridge"
systemd_user_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
service_file="$systemd_user_dir/qqmusic-mpris-bridge.service"
service_template="$project_dir/systemd/qqmusic-mpris-bridge.service.in"

command -v python3 >/dev/null 2>&1 || die "python3 is required"
python3 - <<'PY' >/dev/null 2>&1 || die "python3 venv support is required"
import venv
PY
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1

info "Creating virtual environment: $venv_dir"
mkdir -p "$lib_dir" "$bin_dir"
python3 -m venv "$venv_dir"

info "Installing Python packaging tools"
"$venv_dir/bin/python" -m pip install --upgrade pip setuptools wheel

info "Installing qqmusic-mpris-bridge into the virtual environment"
"$venv_dir/bin/python" -m pip install --upgrade "$project_dir"

info "Linking command: $bin_link"
ln -sfn "$command_path" "$bin_link"

if [[ "$install_service" -eq 1 ]]; then
  [[ -f "$service_template" ]] || die "missing service template: $service_template"
  mkdir -p "$systemd_user_dir"
  "$venv_dir/bin/python" - "$service_template" "$service_file" "$bin_link" <<'PY'
from pathlib import Path
import sys

template = Path(sys.argv[1])
target = Path(sys.argv[2])
executable = sys.argv[3]
target.write_text(template.read_text().replace("@EXECUTABLE@", executable), encoding="utf-8")
PY
  info "Installed systemd user service: $service_file"

  if command -v systemctl >/dev/null 2>&1; then
    if systemctl --user daemon-reload; then
      if [[ "$enable_service" -eq 1 ]]; then
        systemctl --user enable qqmusic-mpris-bridge.service
      fi
      if [[ "$start_service" -eq 1 ]]; then
        systemctl --user restart qqmusic-mpris-bridge.service
      fi
    else
      info "systemd user manager is not available; service was installed but not enabled"
    fi
  else
    info "systemctl not found; service was installed but not enabled"
  fi
fi

info "Installed qqmusic-mpris-bridge."
info "Command: $bin_link"
if [[ "$install_service" -eq 1 ]]; then
  info "Status: systemctl --user status qqmusic-mpris-bridge.service"
fi
