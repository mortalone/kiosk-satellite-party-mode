# 0.1.6

- Measure 45–160 Hz RMS from the already-received stereo PCM; discard the audio after analysis and schedule 20 ms bass frames against Sendspin playback time.
- Detect bass rises independently of vocals/overall loudness; ignore generic server peaks when PCM bass is available.
- Use shorter, darker high-Disco pulses with adaptive relative thresholds that also work at quiet playback levels.
- Retain visualizer-only fallback, original audio roles, missing-frame handling and cover palettes.
- Add live light_delay_ms slider; reschedule buffered frames on the Sendspin loop, without restarting the add-on.
- Test rejection of 1500 Hz energy, scheduled-not-arrival output, quiet bass and repeated kick pulses against loud vocals.
- Physical Sonos/Flex synchronization requires user calibration; this detects bass transients, not a guaranteed BPM or separated kick drum stem.

# 0.1.5

- Receive a 64×64 album cover through Sendspin's artwork role alongside the silent player and visualizer roles; works with encrypted and legacy protocols.
- Add calm Cover Mood with a slowly changing three-color palette and the selected color as fallback.
- Add cover-colors toggle for every music pattern. Audio still controls movement/pulses; configured brightness remains the maximum.
- Bound artwork to 256 KiB/512×512 and process a 32×32 thumbnail off the audio receiving loop. New covers replace pending covers instead of forming a queue.
- Empty artwork clears the palette. Existing Twinkly ownership and restoration behavior are retained.
- Protocol tests include real artwork delivery over both supported transports. Physical Flex color appearance still needs user testing.

# 0.1.4

- Add a live Calm ↔ Disco music slider in ingress, independent of the brightness limit and selected pattern.
- Calm uses slower attack/release; Disco uses faster responses and stronger brightness pulses driven by bass/energy rises and server peak events, without a synthetic beat clock or local FFT.
- Apply pulse contrast to all music patterns; Radial Pulse blends from sustained energy to pronounced onset pulses.
- Use soft sensitivity gain to preserve differences between strong spectrum bands instead of clipping them to the same maximum.
- Limit slider traffic and avoid reasserting Twinkly realtime mode on every adjustment; periodic mode recovery remains active.
- Use elapsed-time smoothing so 20/30 FPS have equivalent response times; missing visualizer data clears the pulse.
- Add `music_punch` (0–100, default 50) for the startup setting. Ingress adjustments apply immediately; configure the startup value to retain it across restarts.
- The user confirmed 0.1.3 works with the mixed group; the new light dynamics still require judging on the physical Flex.

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
