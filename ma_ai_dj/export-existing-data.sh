#!/bin/sh
# Run on the HA host, with Docker access, after stopping the original MA addon.
set -eu
source_container=${1:-addon_d5369777_music_assistant}
destination=${2:-/mnt/data/supervisor/share/ma-ai-dj-import}
case "$source_container" in
  addon_*music_assistant) ;;
  *) echo 'Specify the original Music Assistant addon container.' >&2; exit 1 ;;
esac
if [ "$(docker inspect -f '{{.State.Running}}' "$source_container")" != false ]; then
  echo 'Stop the original Music Assistant addon before copying its database.' >&2
  exit 1
fi
if [ -e "$destination" ]; then
  echo 'Import destination already exists; refusing to overwrite it.' >&2
  exit 1
fi
mkdir -p "$destination"
chmod 700 "$destination"
docker cp "$source_container:/data/." "$destination/"
test -s "$destination/settings.json"
test -s "$destination/library.db"
echo 'Existing MA data copied. Keep the original addon stopped and retain your backup.'
