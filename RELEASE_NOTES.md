## 0.1.15

- Make the guest QR about half its previous default width and integrate it into a compact dark card with a teal heading and muted caption.
- Offer persisted Small / Medium / Large QR sizes under Party menu → Guests, preserving the scan contrast and quiet zone.
- Party Guest 0.2.4 explains per-track ≈ recommendations, uses gentle moving playback bars with reduced-motion settings, and returns ready MA searches without a second fetch.

## Party Guest 0.2.1 · AI DJ 0.1.7 · Party Mode 0.1.14

- Fix the real-MA guest boot crash caused by null metadata images. Missing artist lists and artwork are handled safely.
- Put a per-track recommendation button on the right of queue and result rows in Party Guest and the Kiosk queue. Each button uses its own row's track.
- Keep per-track recommendations independently controlled from similarity text search, including on Kiosk.
- Guest reference requests resolve fresh queue item IDs or the guest's own verified result/index; arbitrary URIs and foreign/expired rows are rejected.
- Party Mode 0.1.14 includes these native changes; the earlier uncompleted 0.1.14 build was never released.

## Party Mode 0.1.14 · Party Guest 0.2.0 · AI DJ 0.1.6

- Give the independent guest page a light MA-inspired layout, cyan search pills, cover art and a live queue with the current track highlighted. Bibliotek is ordinary search without AI; Samme stil and optional AI have plain-language explanations.
- Move guest queue placement and automatic continuation into Party Guest ingress. The guest footer follows the host policy; guest requests cannot override it.
- Automatically fill a short playing queue from favorite tracks, MA similar-track recommendations or an optional AI prompt. Default to one upcoming automatic track; allow 1–5. Prefetch candidates before the tail finishes, discard pending results after new requests, and recheck external MA additions before appending.
- Never resume a paused/stopped player or replace a queue during automatic filling. Favorites cycle after eligible favorites have played; AI receives recent/queued exclusions. Saved continuation remains off after restart unless an explicitly linked HA switch enables it.
- Kiosk publishes one HA switch and three selects for continuation, method, count and guest placement when connected to Party Guest. Controls work while the Party display is closed. Existing HA helpers can alternatively be linked in addon configuration.
- Remove the old continuous-DJ controls from AI ingress; retain its backend for existing automations and its separate manual preview placement selector. AI DJ supplies optional suggestions to Party Guest, and stock Music Assistant remains unchanged.
- Test bounded filling, guest races, pause/stop, persistence and HA helpers; browser checks cover the light page, three modes, host policy and guest isolation; native emulator checks round-trip all four Party HA controls.

## Party Mode 0.1.13 — independent Party Guest 0.1.0

- Separate the Party guest portal from AI DJ. Søg, Similar, current-track recommendations and append-to-queue work without AI DJ installed or Kiosk running.
- Add Party Guest HA add-on with own MA queue/connection, direct browser URL on port 8102 and an ingress link. Optional AI DJ connection only supplies AI results; unavailable AI hides its tab.
- Add a separate Party Guest connection in Kiosk's Guests menu. Existing AI DJ guest links remain a compatibility fallback until configured.
- Direct guest URLs can join the configured queue while access is enabled; own HA permission switches revoke access. Host and MA credentials remain inaccessible to guest capabilities.
- Native emulator scenario verifies custom guest QR with the AI DJ URL cleared. Standalone browser tests verify direct access and ingress with no AI engine.

## Party Mode 0.1.12 and Party AI DJ 0.1.4

- Restore QR destination choice: official Music Assistant guest portal or independent Party guest page. The companion page offers Library, Sonic Similarity, AI DJ and similar-to-current-track, without changing official MA.
- Add six persisted HA switches to show/hide screen settings categories: visualization, music/AI connection, screen controls, guests/QR, sound/EQ and graphics/status. Hide every category to remove the menu button. Search permissions are HA-only.
- Create queue-scoped, expiring guest tokens; never put the companion host API token into a QR. Guests can append verified search results only. The custom page uses its own search throttles, not MA Party request/boost limits.
- Request Kiosk foreground even if a background Activity exists, retry briefly and preserve Party during the screensaver transition. Physical Fotoo validation remains necessary.
- Add guest API isolation, mode/queue/expiry checks, QR token checks and native category/custom-QR smoke scenarios.

## Correction: retain official Music Assistant

- Withdraws the replacement MA add-on and its data migration instructions.
- Keeps Party AI DJ 0.1.3 as an independent HA companion to the official MA API.
- Native MA provider/frontend changes remain development source only; stock MA 2.10.5 cannot install them as an external plugin from this repository.
- No user's running HA/MA installation has been changed.

## Native MA Party AI DJ — 2.10.5-dj.1

- Adds an experimental replacement MA 2.10.5 HA add-on with an explicit, atomic import of existing data and a port conflict guard.
- Pins the matching stable frontend 2.17.297; replaces a development-only access helper with the stable user-filtered music provider API.
- Adds a desktop Party search dialog using the same guest page request/boost actions. Similar can use the current Party track.
- Party AI DJ 0.1.3 exposes HA-controlled search visibility using existing switch/input_boolean entity IDs.
- Requires migration of the existing stopped MA data; no live installation or HA migration has been performed.

Party Mode 0.1.11

- One search button opens Library, Similarity and AI DJ pills with a shared input and explanations. AI DJ uses the working addon API, native cover-art results and the usual queue-position picker; the standalone DJ button is removed.
- Adds saved HA switches Search: Library, Search: Similarity, Search: AI DJ and Similar to current track, without consuming manifest settings. The master Allow music search setting remains authoritative.
- Similarity offers a button based on the track currently playing and optional per-result buttons. Disabling a mode dismisses its open panel and prevents stale results from returning.
- Guest QR always follows the existing Music Assistant Party guest portal. The old alternate AI-addon QR is retired so Guest access no longer points at a separate portal.
- Shows a short QR connection/setup explanation on the screen when no usable QR is available. Checks the selected group's queue before offering a guest link.
- Adds an experimental Music Assistant AI DJ provider and a patch to its existing guest page under ma_ai_dj/. This is source for a customized MA build, not an automatically installable plugin in stock MA. Its results use MA's existing Party request/boost actions.
- Verified Android compilation, queue/QR/playback regressions, and AI job session isolation. Physical Pi/HA setup and the native MA integration still need real-device validation.
