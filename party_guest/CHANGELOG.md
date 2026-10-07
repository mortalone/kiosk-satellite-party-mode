## 0.2.4

- Show a short explanation of the per-track ≈ recommendation button when enabled.
- Make playback bars visibly change height; use a gentler animation with reduced-motion settings and stop on pause.
- Return completed MA search results directly, removing a separate job-fetch request; keep AI polling unchanged.
- Browser tests sample actual bar movement, paused/reduced-motion behavior, legend visibility and the shorter search path.

## 0.2.3

- Normal search includes the MA library and connected catalogs such as Spotify, instead of restricting results to saved library tracks. Rename the tab to Søg and explain its scope.
- Animate small blue bars beside the playing track; stop on pause and respect reduced-motion preferences.
- Bring new search results into view when finding similar music from a queue row far down the page.
- Verify Queen catalog results and playback animation in mobile browser checks.

## 0.2.2

- Let the queue scroll with the page, without a nested scroll area on phones or desktops.
- Explain missing AI search in the host page: missing URL/token, rejected credentials, unreachable service, or disabled AI.
- Show the Kiosk connection directly instead of hiding it in a collapsed section; distinguish Party Guest and AI DJ tokens.

## 0.2.1

- Fix guest startup with MA tracks whose metadata images/artist lists are null; missing artwork no longer hides search and queue.
- Place Find similar buttons at the right of each search result and queue row; use that exact track, not always the playing track.
- Keep per-track recommendations independent of the optional similarity text-search tab.
- Resolve guest references from fresh queue item IDs or the guest's own verified jobs; do not accept arbitrary reference URIs.
- Cover null metadata and row-reference/permission regressions in backend and browser checks.

## 0.2.0

- Light MA-inspired guest layout with Bibliotek / Samme stil / AI, plain-language help and a live highlighted queue.
- Host-owned queue placement reflected in guest text; guests cannot choose a different placement.
- Party-owned automatic continuation from favorite tracks, MA recommendations or optional AI, in batches of 1–5 upcoming tracks (default 1).
- Cancel stale candidates when guests add music; recheck playback/queue before appending. Do not resume paused or stopped players.
- Persist host policy, keep continuation off after restart, and expose authenticated controls for Kiosk's HA switch/selects and optional external HA helpers.
- Favorites cycle without immediate repeats; AI can exclude recent and queued music with AI DJ 0.1.6.

## 0.1.0

- Standalone guest portal independent of Kiosk and Party AI DJ; uses official MA's API.
- Direct `/guest/` browser URL with automatic queue-scoped session and ingress link.
- Own Kiosk connection and API token; optional remote AI search engine.
- Søg and Similar work with no AI service installed; hide AI when unavailable.
- HA controls for access/search permissions, resolved-result append only and expiring guest capabilities.
- Tests cover direct browsing, old session recovery, ingress link, disabled access, queue changes, host isolation and optional AI failures.
