# Installation

1. In Home Assistant, open Settings → Apps/Add-ons → Store → menu → Repositories.
2. Add `https://github.com/mortalone/kiosk-satellite-party-mode`.
3. Install **Twinkly Bridge**. Home Assistant builds the container locally; the first installation can take a few minutes.
4. Set `device_ip` to your Twinkly Flex controller's IPv4 address. Reserve it in your router.
5. Start the add-on and open its web UI. Select **Løbelys** to test individual LED control.

Supported host architectures: amd64 (including Intel N150) and aarch64.
Home Assistant OS/Supervised with the add-on store is required.

# Configuration

| Option | Default | Purpose |
| --- | --- | --- |
| `device_ip` | empty | Twinkly controller IPv4 address |
| `api_token` | empty | Your own secret for automation/audio API; empty disables external API access |
| `brightness` | 30 | Initial brightness, 0–100% |
| `fps` | 20 | Frame rate, 5–30 FPS |
| `speed` | 1 | Initial movement speed, 0.1–5 |
| `sendspin_url` | empty | Direct Music Assistant Sendspin URL, e.g. `ws://192.168.1.10:8927/sendspin` |
| `sendspin_protocol` | auto | Detect classic servers or use the official encrypted Noise client; force `legacy`/`noise` if needed |
| `light_delay_ms` | 0 | Light timing adjustment: positive means later, negative means earlier; −2000 to 2000 ms |
| `music_pattern` | mirror | Initial music style: spectrum, mirror, pulse, wave, particles, tunnel |

Changing configuration requires restarting the add-on. It starts without changing the light.
The web UI runs through Home Assistant ingress, so it needs no separate login.
External API access is optional: configure a long `api_token` and map container TCP
port 8100 to an available host port under Network. The ingress port is not published.
The controller must be reachable over HTTP port 80 and realtime UDP port 7777.

# Using the light

Choose a color, rainbow or chase pattern. Chase is the most useful first test for
individually addressable LEDs. Brightness and speed can be adjusted while a pattern runs.
This release controls LED order, without needing Twinkly's spatial mapping.

**Tilbage til Twinkly** restores the operation mode and brightness captured when the
bridge first connected. Realtime mode cannot be resumed without its original sender,
so a previously active realtime mode restores to off. Stopping the add-on also attempts
restoration. Unexpected power loss cannot run restoration. Test patterns do not upload
or overwrite stored Twinkly movies. The app and Home Assistant integration may compete
with this controller: return control before using them.

# Automation API

Send JSON to `http://HOME_ASSISTANT_IP:HOST_PORT/api/control` with
`Authorization: Bearer YOUR_API_TOKEN` and `Content-Type: application/json`.
Supported modes: `color`, `rainbow`, `chase`, `music`, `off`, `restore`.

```json
{"mode":"chase","color":"#ff4080","brightness":30,"speed":1}
```

HTTP 202 acknowledges the command; consult `GET /api/status` for the applied mode
and connection errors. Example Home Assistant automation configuration:

```yaml
rest_command:
  twinkly_bridge:
    url: "http://HOME_ASSISTANT_IP:8100/api/control"
    method: POST
    headers:
      Authorization: !secret twinkly_bridge_authorization
    content_type: "application/json"
    payload: '{"mode":"{{ mode }}","brightness":{{ brightness | default(30) }}}'
```

Store `twinkly_bridge_authorization: "Bearer YOUR_API_TOKEN"` in `secrets.yaml`.
Call `rest_command.twinkly_bridge` with data `mode: rainbow` (or another supported mode).

# Direct Music Assistant / Sendspin connection

1. Set `sendspin_url` to `ws://YOUR_MUSIC_ASSISTANT_HOST:8927/sendspin`.
   If MA runs on your Home Assistant machine, use that machine's local IP.
   Check that MA's Sendspin provider is enabled and its port is reachable.
2. Restart Twinkly Bridge. Its UI should report **Sendspin forbundet**.
3. In Music Assistant, find the new **Twinkly Bridge** visualization device and
   join it to the active Sendspin player/group carrying your music.
4. Choose **Musik** or a music pattern in the add-on. The UI reports the group,
   clock synchronization and whether visualizer data is arriving.

The add-on receives 32 spectrum bands plus loudness and transient peaks at up to
the selected FPS. It does not decode or play audio and does not depend on Kiosk
Satellite. Future frames are buffered and rendered using the server's playback
timestamps; seeks, pauses, stream ends and reconnects clear old data. Missing data
causes blackout after 1.5 seconds. The timeline is bounded to prevent accumulating
latency. `light_delay_ms` lets you adjust for the actual Flex/network response.

The official `aiosendspin` 9.1.1 client handles encrypted Noise transport and time
synchronization. Receive-only guest access is enabled for this visualizer client;
MA normally approves this automatically. Its stable identity and pairing store
live only in the add-on's private `/data`. No MA control token or player role is
requested. Automatic classic-protocol detection applies only when a server sends
a plaintext `server/hello`; it does not downgrade after an authentication error.
For older servers that wait for a client hello first, select `legacy` explicitly.

A plain Sonos player/group may not carry Sendspin visualizer data. The bridge must
join a Sendspin stream/group, just like MA's Hue light synchronization. The Kiosk
can be part of that group as an existing Sendspin player; it does not process or
forward the light data. Playing independently in the Sonos app is not automatically
captured by this connection.

## Music patterns

| Pattern | Party Mode inspiration | LED behavior |
| --- | --- | --- |
| Neon Spectrum | Spectrum | Color-coded frequency bands along LED order |
| Mirror Spectrum | Mirror | Symmetric spectrum from center to ends |
| Radial Pulse | Radial | Selected color follows bass/overall energy |
| Wave | Waveform | Moving brightness wave driven by music energy |
| Star Particles | Particles | Sparkles driven by energy and transient peaks |
| Neon Tunnel | Tunnel | Repeating outward motion from the center |

These are one-dimensional adaptations, not exact copies of the screen animation.
Sendspin spectrum/loudness data does not include raw waveform samples, so Wave
is an energy-driven wave rather than an oscilloscope. Sensitivity and smoothing
help keep quiet passages visible without rapid flicker. The selected color controls
chase, solid color, pulse, wave, particles and tunnel; spectrum/mirror use their own
frequency palette.

## Optional external audio API

The existing API remains available to other analyzers, but is unnecessary for
direct Sendspin. Send normalized spectrum bands to `POST /api/audio`:

```json
{"bands":[0.2,0.8,0.4,0.1]}
```

The API uses the same bearer token. It accepts 1–128 finite numbers and clamps them
to 0–1. A latest-frame mailbox avoids a growing queue. Choose `music` in the UI.
Do not feed this endpoint concurrently with an active Sendspin source.

# Limitations and troubleshooting

This uses unofficial local Twinkly APIs. Chase output was confirmed on the user's
Flex with 0.1.0; the complete 0.1.1 update still needs a real-device test.
Connection errors appear in the UI and log, with retries every five seconds.
Verify the IP and local network access first. Authentication, firmware or LED protocol
differences may require adaptation after the first hardware test. No firmware update
commands are exposed. No automatic discovery or cloud account is required.

The UI now serializes changes, rejects old status replies and treats color/brightness
as patches to the current effect. Twinkly realtime mode is confirmed periodically,
and recovered if another controller changes it. The UI's **Gendannet realtime** count
helps identify competition from the app or automations. Rejected Twinkly commands
are reported instead of silently assumed successful.

Tests cover the user's chase → green → solid → off → chase sequence, real xled
HTTP authentication and UDP encoding against a mock controller, actual encrypted
Sendspin exchange with the official reference server, classic WebSocket frames,
playback timestamps, silence, pause/seek clearing, and stale UI polling.
