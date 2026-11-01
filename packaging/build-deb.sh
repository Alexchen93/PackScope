#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
version=0.2.0~dev1
destination=${1:-"$project_dir/dist"}
mkdir -p "$destination"
destination=$(CDPATH= cd -- "$destination" && pwd)
stage=$(mktemp -d "${TMPDIR:-/tmp}/packscope-deb.XXXXXX")
trap 'rm -rf "$stage"' EXIT HUP INT TERM
mkdir -p "$stage/DEBIAN" "$stage/usr/lib/packscope" "$stage/usr/bin" "$stage/usr/share/applications" "$stage/usr/share/icons/hicolor/scalable/apps" "$stage/usr/share/doc/packscope"
cp -a "$project_dir/packscope" "$project_dir/bauh" "$stage/usr/lib/packscope/"
find "$stage/usr/lib/packscope" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$stage/usr/lib/packscope" -type f -name '*.pyc' -delete
cp "$project_dir/packaging/packscope.desktop" "$stage/usr/share/applications/"
cp "$project_dir/packscope/assets/packscope.svg" "$stage/usr/share/icons/hicolor/scalable/apps/"
cp "$project_dir/LICENSE" "$stage/usr/share/doc/packscope/copyright"
cat > "$stage/usr/bin/packscope" <<'EOF'
#!/bin/sh
export PYTHONPATH="/usr/lib/packscope${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1
exec python3 -m packscope.app "$@"
EOF
chmod 755 "$stage/usr/bin/packscope"
cat > "$stage/DEBIAN/control" <<EOF
Package: packscope
Version: $version
Section: admin
Priority: optional
Architecture: all
Maintainer: PackScope contributors
Depends: python3 (>= 3.11), python3-pyqt5, python3-gi, python3-requests, python3-yaml, python3-dateutil, python3-colorama, libqt5svg5, pkexec
Description: Unified software management interface for Ubuntu
 PackScope provides a graphical interface for managing applications from
 APT, Flatpak, Snap, AppImage and supported developer package managers.
 Based on bauh; see the project documentation for scope and limitations.
EOF
dpkg-deb --build --root-owner-group "$stage" "$destination/packscope_${version}_all.deb"
