# 0.1.1

- Fix playback being aborted during track lookup: legacy getLyrics now returns the standard not-found response that Music Assistant handles.
- Add a regression test for track resolution, missing lyrics and subsequent audio playback.

# 0.1.0

- Initial standalone Home Assistant app exposing YouTube as an OpenSubsonic source.
- Ordinary YouTube search and exact video-ID/link lookup.
- JSON/XML protocol replies and persistent catalog, favorites and source playlists.
- On-demand MP3 conversion with bounded cache and HTTP Range support.
- Danish ingress helper for importing a specific video.
- Official Music Assistant remains independently installed and updated.
