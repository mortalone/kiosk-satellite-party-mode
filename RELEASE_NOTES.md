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
