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
