#!/usr/bin/env bash
set -e

UUID="prayer-time-clock@askaerlangga.github.io"
EXT_DIR="$HOME/.local/share/gnome-shell/extensions/$UUID"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing GNOME Shell Extension: $UUID"
mkdir -p "$HOME/.local/share/gnome-shell/extensions"

# Remove old installation if exists
if [ -d "$EXT_DIR" ] || [ -L "$EXT_DIR" ]; then
    rm -rf "$EXT_DIR"
fi

# Copy extension files
cp -r "$SRC_DIR" "$EXT_DIR"
rm -f "$EXT_DIR/install.sh"

echo "Extension installed to: $EXT_DIR"

if command -v gnome-extensions >/dev/null 2>&1; then
    echo "Enabling extension..."
    gnome-extensions enable "$UUID" || true
    echo "Done! If the extension does not appear immediately, please reload GNOME Shell (Alt+F2 -> r on X11 or log out/log in on Wayland)."
else
    echo "Done! Please log out and log in again, then enable it via 'gnome-extensions enable $UUID' or GNOME Extensions app."
fi
