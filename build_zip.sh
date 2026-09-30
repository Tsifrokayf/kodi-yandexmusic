#!/bin/sh
# Build an installable Kodi zip for the addon AND refresh the local update
# repository in ~/Desktop/kodi-repo.
# Usage: sh build_zip.sh [addon_dir]   (default: ./plugin.audio.yandexmusic)
#
# 1) Patch-version in addon.xml is bumped on EVERY build, so Kodi's
#    "Check for updates" always sees a newer version than the installed one.
# 2) The manual-install zip goes to ~/Desktop with a UNIQUE timestamped name:
#    Kodi caches zip listings by file path+contents in memory, so rebuilding a
#    zip under the same path while Kodi runs makes installs read stale indexes
#    and fail with "Failed to open file". A fresh name avoids that.
# 3) The repository keeps the CANONICAL zip name (<id>-<version>.zip) under
#    kodi-repo/<id>/ — that is the layout Kodi builds download URLs from
#    (datadir + id + "/" + id + "-" + version + ".zip").
#
# Serve the repository for Kodi: data lives in ./docs, published as
#   https://<user>.github.io/<repo>/
# by GitHub Pages (Kodi can only update over http/https).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ADDON_DIR="${1:-$HERE/plugin.audio.yandexmusic}"
NAME="$(basename "$ADDON_DIR")"
OUT_DIR="$HOME/Desktop"
REPO_DIR="$HERE/docs"

# bump patch version: 0.1.0 -> 0.1.1 (only the root <addon ... version=...>)
VERSION=$(grep -o '<addon [^>]*version="[^"]*"' "$ADDON_DIR/addon.xml" | grep -o 'version="[^"]*"' | cut -d'"' -f2)
NEW_VERSION=$(echo "$VERSION" | awk -F. '{printf "%d.%d.%d", $1, $2, $3 + 1}')
sed -i '' "s/\(<addon [^>]*version=\)\"$VERSION\"/\1\"$NEW_VERSION\"/" "$ADDON_DIR/addon.xml"
VERSION="$NEW_VERSION"

# drop previous builds (old flat name lives in $HERE, newer ones on Desktop)
rm -f "$HERE/${NAME}-"*.zip "$OUT_DIR/${NAME}-"*.zip
OUT="$OUT_DIR/${NAME}-${VERSION}-$(date +%Y%m%d-%H%M%S).zip"
cd "$(dirname "$ADDON_DIR")"
find "$ADDON_DIR" -name '__pycache__' -type d -prune -exec rm -rf {} +
zip -qr "$OUT" "$NAME" \
  -x '*.pyc' -x '*__pycache__*' -x '*.DS_Store' -x "$NAME/tests/*"

# refresh local repository
mkdir -p "$REPO_DIR/$NAME"
rm -f "$REPO_DIR/$NAME/${NAME}-"*.zip
cp "$OUT" "$REPO_DIR/$NAME/${NAME}-${VERSION}.zip"
{
  echo '<addons>'
  sed '1d' "$ADDON_DIR/addon.xml"   # drop the <?xml ...?> declaration line
  echo '</addons>'
} > "$REPO_DIR/addons.xml"
shasum -a 256 "$REPO_DIR/addons.xml" | awk '{print $1}' > "$REPO_DIR/addons.xml.sha256"

# publish to GitHub Pages (docs/ is the Pages root); commit everything so
# source edits are never left behind in the working tree
if git -C "$HERE" rev-parse --is-inside-work-tree >/dev/null 2>&1 &&
   git -C "$HERE" remote get-url origin >/dev/null 2>&1; then
  git -C "$HERE" add -A
  git -C "$HERE" commit -m "Publish $NAME $VERSION" >/dev/null 2>&1 || true
  git -C "$HERE" push origin HEAD >/dev/null 2>&1 ||
    echo "WARN: git push failed ( Pages will be updated on next push )"
fi

echo "Version: $VERSION (bumped from previous build)"
echo "Built:   $OUT"
echo "Repo:    $REPO_DIR/addons.xml + $NAME/$NAME-$VERSION.zip"
