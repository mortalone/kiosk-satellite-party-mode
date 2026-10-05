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

# Music bridge

The receiver is ready; the Party Mode/Kiosk sender still needs to be connected.
Music mode does not listen to a microphone or retrieve sound from media_player entities.
An audio analyzer must send normalized spectrum bands to `POST /api/audio`:

```json
{"bands":[0.2,0.8,0.4,0.1]}
```

The API uses the same bearer token. It accepts 1–128 finite numbers and clamps them
to 0–1. A latest-frame mailbox avoids a growing queue. Choose `music` in the UI to
display these bands along the LED strip. After 1.5 seconds without new data the strip
goes dark. No phone or microphone is required when Kiosk's analyzer is connected.

# Limitations and troubleshooting

This uses unofficial local Twinkly APIs. Physical Flex compatibility has not been
verified. Connection errors appear in the UI and log, with retries every five seconds.
Verify the IP and local network access first. Authentication, firmware or LED protocol
differences may require adaptation after the first hardware test. No firmware update
commands are exposed. No automatic discovery or cloud account is required.

The Python behavior and simulated device/API paths are tested; installation and
real LED output must still be verified on Home Assistant and your controller.
