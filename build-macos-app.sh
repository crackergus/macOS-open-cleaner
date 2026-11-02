#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BUILD_DIR="$ROOT_DIR/.build"
APP_DIR="$HOME/Applications"
DIST_DIR="$ROOT_DIR/dist"
APP_NAME="MACOS OPEN CLEANER"
APP_PATH="$APP_DIR/$APP_NAME.app"
VERSION=$(tr -d '[:space:]' < "$ROOT_DIR/VERSION")

if ! printf '%s\n' "$VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
	printf 'Versione non valida in VERSION: %s\n' "$VERSION" >&2
	exit 1
fi

mkdir -p "$APP_DIR" "$DIST_DIR"
python3 -m venv "$BUILD_DIR/venv"
"$BUILD_DIR/venv/bin/python" -m pip install -r "$ROOT_DIR/requirements-build.txt"
APP_ARCH=$("$BUILD_DIR/venv/bin/python" -c 'import platform; print(platform.machine())')
ARCHIVE_PATH="$DIST_DIR/MACOS-OPEN-CLEANER-$VERSION-macos-$APP_ARCH.zip"

"$BUILD_DIR/venv/bin/python" -m PyInstaller \
	--noconfirm \
	--clean \
	--windowed \
	--name "$APP_NAME" \
	--osx-bundle-identifier "com.apinfosec.macosopencleaner" \
	--add-data "$ROOT_DIR/VERSION:." \
	--workpath "$BUILD_DIR/work" \
	--specpath "$BUILD_DIR" \
	--distpath "$APP_DIR" \
	"$ROOT_DIR/macos-open-cleaner.py"

PLIST_PATH="$APP_PATH/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$PLIST_PATH"
if /usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$PLIST_PATH" >/dev/null 2>&1; then
	/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $VERSION" "$PLIST_PATH"
else
	/usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $VERSION" "$PLIST_PATH"
fi

if command -v codesign >/dev/null 2>&1; then
	xattr -cr "$APP_PATH"
	codesign --force --deep --sign - "$APP_PATH"
	codesign --verify --deep --strict "$APP_PATH"
fi

rm -f "$ARCHIVE_PATH" "$ARCHIVE_PATH.sha256"
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ARCHIVE_PATH"
shasum -a 256 "$ARCHIVE_PATH" > "$ARCHIVE_PATH.sha256"

printf 'Versione: %s\nApp standalone: %s\nArchivio: %s\nChecksum: %s\n' \
	"$VERSION" "$APP_PATH" "$ARCHIVE_PATH" "$ARCHIVE_PATH.sha256"