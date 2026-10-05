# 0.1.3

- Register as both a silent audio player and visualizer by default so Music Assistant can select a playback output protocol.
- Accept stereo 16-bit PCM at 48/44.1 kHz, discard audio immediately and continue rendering only server-provided visualizer frames.
- Report player timing/state and acknowledge volume/mute changes without changing LED brightness.
- Send the initial availability/state after guest playback activation, avoiding a race that could leave the server's visualizer binary gate closed.
- Add a separate audio-packet counter in the control panel to distinguish audio reception from visualization reception.
- Preserve the existing Sendspin identity; `sendspin_player: false` restores the previous visualizer-only behavior.
- Cover dual-role negotiation, actual PCM reception, simultaneous visualizer frames and volume/mute acknowledgements against classic WebSocket and the official encrypted reference server.
- Mixed Pi/Sonos universal-group playback still requires hardware verification; this release does not claim that group membership or native Sonos timing is fixed.

# 0.1.2

- Handle non-JSON ingress/proxy responses with a readable HTTP status instead of a JSON parser exception.
- Mark all displayed measurements as unknown when a status request fails; do not leave a stale frame counter looking current.
- Bound browser requests to eight seconds and recover automatically on the next poll.
- Update Sendspin clock status independently of incoming music frames.
- Add timestamps, logger names and encrypted connection lifecycle events to diagnostics.
- This diagnostic release does not claim to fix Twinkly token rejection or universal-group membership.

# 0.1.1

- Direct Music Assistant Sendspin visualizer client; no Kiosk audio relay or local FFT.
- Timestamped frame buffering, clock synchronization, reconnects and stream clearing.
- Six Party Mode inspired LED patterns with sensitivity and smoothing.
- Serialize rapid UI adjustments and reject stale polling replies.
- Color/brightness patches preserve the selected effect.
- Confirm/recover Twinkly realtime mode and report rejected device commands.
- Allow restoration of modern Twinkly color mode with xled 0.7.0.
- Regression tests for green chase, solid color and off → chase, plus official Sendspin server tests.

# 0.1.0

- Initial Home Assistant add-on with isolated, pinned xled/xled_plus dependencies.
- Ingress panel for color, rainbow, chase, brightness, speed, off and restore.
- Authenticated control API and latest-frame audio spectrum receiver.
- Bounded HTTP calls, connection retries and stale-audio blackout.
- Initial release for hardware testing; Kiosk audio sender not included yet.
