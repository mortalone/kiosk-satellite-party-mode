# YouTube Bridge for Music Assistant

This experimental app exposes ordinary YouTube videos as an OpenSubsonic source. Keep the official Music Assistant app running. This app is independent and does not modify its container. No paid YouTube Music subscription or Google login is required by the bridge; YouTube may still block anonymous extraction.

## Install

Use the existing app repository:
`https://github.com/mortalone/kiosk-satellite-party-mode`

Refresh the Home Assistant App Store repository list. Install **YouTube Bridge for Music Assistant**. Set a username and a unique password (at least 8 characters), save, and start. The first install builds an image locally and can take several minutes. The app exposes port 8102, independent from MA's ports. If necessary change the host port in Network and use that port below.

## Connect the official Music Assistant

1. Settings -> Music Sources -> Add source -> **OpenSubsonic Media Server Library**.
2. Base URL: `http://192.168.0.18` (replace with your Home Assistant host IP).
3. Port: `8102`. Server Path: leave empty.
4. Enter the username/password from the bridge configuration. Leave API token blank. Legacy authentication can remain off.
5. Disable Podcasts and Radio Stations (also disable those library sync categories). Optionally disable source recommendations, since this bridge does not generate similar tracks.
6. Name the source **YouTube**. Search inside MA by title, uploader, cover or remix. Results come from ordinary YouTube, not only YouTube Music's Songs filter.
7. Add tracks to a playlist created in MA's own library. Such playlists can mix Spotify tracks and YouTube tracks. A playlist owned by Spotify cannot hold YouTube items. The bridge's own source playlists accept only its YouTube IDs.

Each video ID persists in `/data/catalog.db`, so saved MA playlist entries still resolve after restarting the bridge. Searches persist metadata, not all audio. Source library synchronization enumerates videos explicitly imported/starred through the bridge; normal MA searches also find other videos. A video's uploader is shown as its artist when YouTube does not supply an artist tag. Each video has a synthetic single-track album; it is not a verified studio discography.

## Exact videos / Shorts

Search for a full YouTube watch/shorts/youtu.be URL in MA. This resolves the exact video rather than finding another version. MA may interpret some service URLs before forwarding a query: if so, use the video's 11-character ID in the search field, e.g. `3VaZ-4AG-f0`. Alternatively open the app's Home Assistant ingress page, paste the link into **Tilføj video**, then search its title or ID in MA or synchronize the source library.

The ingress page is a helper; regular search, playback, mixed queues and MA playlists are handled inside MA. The helper is on a separate internal port and is not exposed by the app's host port mapping. The Subsonic API requires authentication. Credentials travel over local HTTP; do not expose port 8102 to the internet.

## Optional lyrics (0.1.2+)

The app exposes the concrete video's captions as lyrics via the OpenSubsonic `songLyrics` extension. In app Configuration, **Hent sangtekster** (`lyrics_enabled`) defaults to on; **Tillad automatiske undertekster** (`allow_auto_lyrics`) defaults to off. Turn the first off to disable all caption lookup. The second allows automatic YouTube captions when uploader captions are unavailable. These may contain recognition errors, speech, or audience noise; uploader captions may also contain speech rather than song lyrics. No YouTube Music lyric matching is performed.

The bridge prefers the original language when YouTube identifies it, otherwise an available caption track. Machine-translated tracks marked with `tlang` are excluded. JSON3 and WebVTT timestamps are preserved as line-level timing for MA; no alignment to a different recording is attempted.

Lyrics are cached in the persistent SQLite catalog for seven days, absent captions for one hour, and failed requests for five minutes. The automatic-caption setting has a separate cache, so disabling it cannot return a previously cached automatic transcript. A request waits at most eight seconds, then returns no lyrics while lookup finishes in the background. Caption lookup runs separately from audio extraction, with at most two workers; its errors never propagate as playback errors. If the first lookup was slow, text can appear after the track metadata is refreshed in MA. MA also caches metadata, so restarting the bridge alone does not necessarily refresh text for already loaded tracks.

After updating, reload the YouTube/OpenSubsonic source in MA (or restart MA) so it detects the new `songLyrics` capability. This enables timed text in MA; display in another client, including the Kiosk lyric overlay, depends on that client's lyric support. No change to that client is included in this release.

## Queue prefetch (0.1.3+)

Enable **Hent kommende numre på forhånd** (`prefetch_enabled`, default on) and enter the direct **Music Assistant-serveradresse** (`music_assistant_url`), typically `http://192.168.0.18:8095`, and a **Music Assistant-token** (`music_assistant_token`). Use an MA access token, not a Home Assistant token; generate it in MA's user/profile settings. It needs permission to read queues. The URL must be the direct MA server, not the HA ingress URL on port 8123. No request is made until both URL and token are configured. Save and restart the bridge. The ingress helper shows connection state and how many upcoming tracks are cached, without exposing the token.

The bridge polls MA every ten seconds using only `player_queues/all` and `player_queues/items`. It reads playing/paused or active queues, scans the next 50 queue positions after the current item, and prepares the next **Antal kommende YouTube-numre** (`prefetch_tracks`, default 2, configurable 1–5) per queue, with at most six target tracks across all rooms. Only OpenSubsonic items already known to this bridge are eligible; Spotify and unrelated sources are skipped. It never changes the queue, starts a player or skips a track.

Downloads are sequential and share the normal audio cache. Direct uncached playback cancels other background downloads (including conversion), while playing the track already being prepared reuses its existing download. Reads of cached audio do not interrupt prefetch. Queue changes cancel obsolete background work; failed prefetch attempts wait five minutes before retrying. Disconnecting MA stops background work, while ordinary source playback remains available. Completed files stay in the bounded cache and may be evicted when space is needed.

This hides loading time when a queued track has finished preparing before its turn. It cannot eliminate first-play latency for a new track selected directly, a rapid skip, or a slow/blocked YouTube download. Queue polling and priority behavior are tested with fixtures; connection to the user's actual MA queues still needs verification after setup.

## Audio cache and limitations

Audio is fetched on demand, converted to stereo MP3 at 192 kbps / 44.1 kHz, and stored in a bounded cache for reliable HTTP Range requests, seeking and repeat playback. The first play waits for downloading/converting the track. This is not instantaneous direct streaming. Cached playback starts faster. MP3 conversion cannot improve the source quality. The cache is separate from the persistent catalog: eviction removes audio, not playlist IDs.

Default cache is 512 MB; inactive files are evicted oldest first. Active files are protected. At most one audio generation runs at a time; search and metadata requests have a concurrency limit. Temporary downloads/conversion need additional disk space beyond the cache budget. yt-dlp attempts to reject oversized source files; the configured cache limit is enforced on completed audio files. It is not a hard disk quota for temporary files. Long videos (default >120 minutes), upcoming videos and live streams are excluded.

Private/age-restricted/members-only videos are not guaranteed. Anonymous playback can fail with bot verification or unavailable formats. In that case read the bridge log; a successful protocol test does not guarantee YouTube access from your IP. yt-dlp and its JavaScript helper are bundled with a Node runtime; updating their pinned version may be needed after YouTube changes. No automatic edits of the MA server are used.

Optional cookies can be placed as `/data/cookies.txt` by an administrator inside this app's private data volume; there is deliberately no default requirement and no public cookie upload endpoint. Cookies do not override access restrictions on your account.

## Validation status

The protocol is tested against **py-opensonic 10.4.1**, the client used by MA 2.10.5. Tests cover login, JSON/XML replies, search, album/artist lookup, persistent video IDs, playlists, authenticated MP3 Range playback, and caption parsing/cache/policy/failure handling using controlled fixtures. Live YouTube extraction and an actual Spotify+YouTube mixed playlist on the user's HA installation must still be tested after installation. This is an initial experimental release, not a claim of verified end-to-end playback.
