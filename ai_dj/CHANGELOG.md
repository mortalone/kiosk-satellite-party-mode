## 0.1.8

- Include the library and connected catalogs in normal guest search; keep Similar restricted to Sonic Similarity.

## 0.1.7

- Share the verified per-track guest recommendation API and permission handling with Party Guest 0.2.1; legacy embedded guest UI remains compatible.

## 0.1.6

- Party Guest owns guest placement and automatic continuation. Remove legacy continuous controls from AI ingress; retain backend compatibility for existing automations.
- Explain that the AI ingress placement selector applies only to manual selections from that page.
- Accept bounded recent/queued exclusions from Party Guest for varied automatic AI suggestions.
- Share guest capability checks with the independent portal.

## 0.1.5
- Retain the embedded guest endpoints for existing connections while the independent Party Guest add-on hosts new guest pages.
- Share the guest frontend/capability contract with the independent portal. Party Guest can use AI DJ 0.1.3+ as an optional remote engine; Søg and Similar do not require it.

## 0.1.4
- Add a separate `/guest/` page with Library, Similar, AI DJ and similar-to-current-track.
- Add authenticated guest-link creation for Kiosk Party 0.1.12; QR contains a dedicated six-hour queue capability, never the host API token.
- Limit guests to verified search results appended to the configured queue. Reject disabled modes, changed queues, expired/unknown jobs and duplicate additions.
- Retain the host interface and official Music Assistant server unchanged.

## 0.1.3
- Expose authenticated search mode configuration for the native MA bridge, controlled by existing HA switches or input booleans.

# 0.1.2

- Show queue placement before search: add, next, play now, replace upcoming, replace all. Replace all requires explicit confirmation.
- Add host-controlled continuous DJ: rolling batches of at most 8, check queue every 20s, refill when 3 or fewer tracks remain, two-minute generation/retry spacing.
- Exclude recent DJ tracks and queued items; pass recent artist/title pairs to the AI for variety.
- Suspend on player pause/stop; retain queue when stopping DJ and never enqueue a stale in-flight result after stop. Remain off after add-on restart.
- Restrict persistent DJ controls to HA ingress; authenticated guests retain one-shot queue actions.
- Test 24 hours of simulated playback, stop during generation, pause/resume, full queues, bounded retries, repeat exclusion and replacement confirmation.

# 0.1.1

- Add an ingress-only selector for existing HA AI Task entities supporting text generation. Persist selection across restarts; guest API cannot list or change HA AI settings.
- Require explicit AI entity selection and show an actionable HA provider error instead of raw HTTP 500.
- Resolve configured HA media_player entity to its active_queue when enqueueing.
- Make unused AI/guest configuration fields optional.

# 0.1.0

- Add diverse natural-language playlists with HA AI Task or an OpenAI-compatible model.
- Resolve real artist/title pairs through Music Assistant and skip uncertain/unavailable matches.
- Add preview, per-track selection and add/next/play choices for a fixed MA queue.
- Add ingress, optional authenticated guest/Kiosk page and a shared automation API.
- Explicit requested years filter AI candidates; display year uncertainty separately from verified catalog identity.
- Tests cover both AI transports, exact matching, missing tracks, years and resolved-only enqueue.
