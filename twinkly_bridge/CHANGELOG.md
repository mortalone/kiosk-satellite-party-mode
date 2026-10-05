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
