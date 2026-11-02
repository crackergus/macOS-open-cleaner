#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BUILD_DIR="$ROOT_DIR/.build"
APP_DIR="$HOME/Applications"
APP_PATH="$APP_DIR/MACOS OPEN CLEANER.app"

mkdir -p "$APP_DIR"
python3 -m venv "$BUILD_DIR/venv"
"$BUILD_DIR/venv/bin/python" -m pip install -r "$ROOT_DIR/requirements-build.txt"
"$BUILD_DIR/venv/bin/python" -m PyInstaller \
	--noconfirm \
	--clean \
	--windowed \
	--name "MACOS OPEN CLEANER" \
	--osx-bundle-identifier "com.apinfosec.macosopencleaner" \
	--workpath "$BUILD_DIR/work" \
	--specpath "$BUILD_DIR" \
	--distpath "$APP_DIR" \
	"$ROOT_DIR/macos-open-cleaner.py"

if command -v codesign >/dev/null 2>&1; then
	xattr -cr "$APP_PATH"
	codesign --force --deep --sign - "$APP_PATH"
fi

printf 'App standalone creata: %s\n' "$APP_PATH"