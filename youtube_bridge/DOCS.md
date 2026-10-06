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

## Audio cache and limitations

Audio is fetched on demand, converted to stereo MP3 at 192 kbps / 44.1 kHz, and stored in a bounded cache for reliable HTTP Range requests, seeking and repeat playback. The first play waits for downloading/converting the track. This is not instantaneous direct streaming. Cached playback starts faster. MP3 conversion cannot improve the source quality. The cache is separate from the persistent catalog: eviction removes audio, not playlist IDs.

Default cache is 512 MB; inactive files are evicted oldest first. Active files are protected. At most one audio generation runs at a time; search and metadata requests have a concurrency limit. Temporary downloads/conversion need additional disk space beyond the cache budget. yt-dlp attempts to reject oversized source files; the configured cache limit is enforced on completed audio files. It is not a hard disk quota for temporary files. Long videos (default >120 minutes), upcoming videos and live streams are excluded.

Private/age-restricted/members-only videos are not guaranteed. Anonymous playback can fail with bot verification or unavailable formats. In that case read the bridge log; a successful protocol test does not guarantee YouTube access from your IP. yt-dlp and its JavaScript helper are bundled with a Node runtime; updating their pinned version may be needed after YouTube changes. No automatic edits of the MA server are used.

Optional cookies can be placed as `/data/cookies.txt` by an administrator inside this app's private data volume; there is deliberately no default requirement and no public cookie upload endpoint. Cookies do not override access restrictions on your account.

## Validation status

The protocol is tested against **py-opensonic 10.4.1**, the client used by MA 2.10.5. Tests cover login, JSON/XML replies, search, album/artist lookup, persistent video IDs, playlists, and authenticated MP3 Range playback using controlled YouTube fixtures. Live YouTube extraction and an actual Spotify+YouTube mixed playlist on the user's HA installation must still be tested after installation. This is an initial experimental release, not a claim of verified end-to-end playback.
