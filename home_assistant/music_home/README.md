# Music Home 0.1.0

A Spotify-inspired, cover-first Lovelace card for the family's everyday music view. Independent of Party Mode, Party Guest and AI DJ. Keeps the official Music Assistant and uses the signed-in HA connection: no MA URL, token, new add-on or frontend build tools are required.

- Home: eight compact shortcuts plus cover rails for playlists, albums, favorite tracks and favorite radio stations.
- Search: debounced global MA search across the connected providers, with covers and track rows.
- Library: playlist / album / artist / favorites / radio / podcast / audiobook tabs; list or cover grid and pagination.
- Collections: inspect tracks without starting playback. **Spil** replaces the queue with the selected collection, **Som næste** inserts next, and **Tilføj til kø** appends. Tapping an individual track starts it via MA's `play` queue option; the adjacent + appends it.
- Mini player: previous / pause / next, selected MA speaker state and optional volume slider.
- Optional **Åbn Spotify-app** link for Kiosk Satellite's `app://com.spotify.music` scheme. Requires a host version supporting app links and an installed/allowed Spotify app. It launches Spotify; it does not select an output or log in. In ordinary browsers keep this option off.

This reproduces a familiar layout, not Spotify's private recommendation data, daily mixes, personal account selector or playlist editor. Content is the library and search exposed by MA. It does not manufacture recommendations or change playback on startup.

## Install

1. Download `music-home-card.js` from the Music Home release. Copy it to `/config/www/music-home-card.js` in HA (create `www` if needed).
2. Add a dashboard resource: **Settings → Dashboards → menu → Resources** (advanced mode may need enabling). URL `/local/music-home-card.js?v=0.1.0`, type **JavaScript module**. In YAML-managed dashboards the same resource is `{url: /local/music-home-card.js?v=0.1.0, type: module}`.
3. Reload the dashboard. Add **Music Home** from the card picker. Choose **Music Assistant's** media_player for Stueetagen, not the original Sonos entity. The visual editor supplies a filtered entity picker. No exact entity ID is assumed.
4. For the full-screen version, create a new dashboard/view and use `dashboard.yaml` as a starting point. Replace the example `media_player.stueetagen` with the actual MA entity. This is an example, not a claim that this entity exists.
5. Open the new view on the tablet and set that view's URL as the Kiosk start/home page. Keep the existing dashboard and Party Mode available separately. Selecting this dashboard as the HA user's default is also possible; this download does not change either setting automatically.

```yaml
type: custom:music-home-card
entity: media_player.stueetagen  # example: replace with your MA entity
name: Musik i huset
start_view: home               # home, library or search
spotify_app: false             # enable only in Kiosk Satellite
height: calc(100dvh - 64px)     # use e.g. 850px for a card in a regular view
```

The HA **Music Assistant integration** must expose `music_assistant.get_library`, `music_assistant.search` and `music_assistant.play_media`. Verified against Home Assistant 2026.10.0 source. Installing only the MA add-on does not add these HA actions. The card resolves the integration config entry from the selected entity; optional `config_entry_id` can be supplied explicitly for unusual setups. Normal HA permissions still apply.

## Behavior and performance

The player follows HA push updates. Library results are bounded, cached for 60 seconds and refreshed with the refresh button; there is no periodic background library polling. Covers load lazily, missing artwork falls back to a colored tile, and HA push updates do not replace the search field or interrupt scrolling. The full-screen panel has one vertical content scroll surface plus horizontal cover rails. No iframe, embedded MA application, animation loop or AI processing is used.

Cover URLs come from MA. On the local HTTP dashboard they can load directly; on a remote HTTPS dashboard, HTTP-only MA image URLs may be blocked as mixed content. A secure reachable MA image endpoint is required there. The miniplayer can use HA's own player image proxy.

## Verification

Playwright checks authenticated request shapes, read-only startup, navigation, next/add/replace queue placement, artist metadata with null lists, search debounce and stale replies, HTML escaping, pause/volume, reconfiguration, error recovery and portrait / landscape / phone layouts. The tests use mock HA and MA and do not verify the user's live library, Android app launch or speakers. Preview covers and music metadata are demonstration fixtures, not the user's library.

Primary API references: [HA MA services](https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/components/music_assistant/services.py), [response schemas](https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/components/music_assistant/schemas.py), [browse implementation](https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/components/music_assistant/media_browser.py).
