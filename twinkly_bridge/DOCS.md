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
| `sendspin_player` | true | Register as a silent PCM audio receiver plus visualizer for group compatibility; false restores visualizer-only mode |
| `light_delay_ms` | 0 | Light timing adjustment: positive means later, negative means earlier; −2000 to 2000 ms |
| `music_punch` | 50 | Initial Calm ↔ Disco setting, 0–100; independent of maximum brightness |
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
3. In Music Assistant, find **Twinkly Bridge**. With `sendspin_player: true`
   (the default), it registers as an audio receiver and visualizer. Try adding it
   to your existing universal group. Stop and restart the group after changing
   membership. Do not create a new group just for this test.
   With `sendspin_player: false`, join it to an active native Sendspin player/group.
4. Choose **Musik** or a music pattern in the add-on. The UI reports the group,
   clock synchronization and whether visualizer data is arriving.

The add-on receives 32 spectrum bands plus loudness and transient peaks at up to
the selected FPS. With `sendspin_player: true`, it also advertises a player role
and accepts stereo 16-bit PCM at 48 or 44.1 kHz. It counts and discards incoming
audio after measuring bass and short spectral attack features; it has no sound
output or microphone. Timestamped PCM features drive pulses, while server-provided
visualizer data supplies the frequency layout. It does not depend on Kiosk
Satellite. The additional PCM stream uses network bandwidth (about 192 kB/s at
48 kHz). Player volume and mute are acknowledged for protocol compatibility;
they do not control LED brightness, which is adjusted in the add-on. Future frames are buffered and rendered using the server's playback
timestamps; seeks, pauses, stream ends and reconnects clear old data. Missing data
causes blackout after 1.5 seconds. The timeline is bounded to prevent accumulating
latency. `light_delay_ms` lets you adjust for the actual Flex/network response.

The official `aiosendspin` 9.1.1 client handles encrypted Noise transport and time
synchronization. Receive-only guest access is enabled for the playback/visualizer client;
MA normally approves this automatically. Its stable identity and pairing store
live only in the add-on's private `/data`. The identity is preserved on upgrade.
No MA control token, controller role or source role is requested. Automatic classic-protocol detection applies only when a server sends
a plaintext `server/hello`; it does not downgrade after an authentication error.
For older servers that wait for a client hello first, select `legacy` explicitly.

A plain Sonos player/group does not automatically provide a Sendspin visualizer
feed. The default silent-player mode is intended to let a universal group start a
separate Sendspin stream for the bridge while playing on Sonos/Pi members. This
needs verification on the actual mixed group; acceptance does not guarantee
visualizer delivery or synchronization with native Sonos. If only **Lydpakker**
increases but **Frames** remains zero, the audio role works but visualizer delivery
is still missing. Disable `sendspin_player` to return to the previous visualizer-only
behavior. The Kiosk does not process or forward the light data. Playing independently in the Sonos app is not automatically
captured by this connection.

## Calm ↔ Disco

The ingress **Roligt ↔ Disco** slider applies immediately to every music pattern.
At 0, transitions are softer and spectrum bands fade slowly. At 100, the response
is faster, with a dimmer background and stronger pulses from bass/energy rises
(spectral attacks with PCM; bass/energy rises and Sendspin peaks in visualizer-only
mode). Radial Pulse becomes the most obvious full-strip pulse;
Mirror/Spectrum keep their frequency layout but gain stronger brightness contrast.
Wave/Particles/Tunnel also gain movement speed. This is onset detection, not BPM
tracking or a predefined beat loop. Held tones do not fabricate repeated beats.

Brightness remains the maximum device setting. Sensitivity uses a soft gain curve
that preserves differences between strong bands. Speed still controls moving
patterns. The slider does not change the selected pattern, mode or brightness.
`music_punch` sets the initial value after restart; ingress changes are session settings.

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
Flex with 0.1.0. Direct Sendspin visualization was confirmed on the user's Flex
with 0.1.1 through both a browser player and the Pi Sendspin player. Membership
retention under a universal group was unresolved in 0.1.1/0.1.2. Version 0.1.3
adds the silent player role for a hardware compatibility test. Registration, PCM
reception and simultaneous visualization pass against the official Sendspin
reference server, and the user confirmed it works in the mixed group. The new 0.1.4 light dynamics
still require judging on the physical Flex.
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

## Albumcover · 0.1.5

Vælg **Cover Mood** i ingress for et roligt lys i coverets farver, uafhængigt af
lydens styrke. Eller slå **Coverfarver** til under **Musik** for at farve det valgte
musikmønster med coverpaletten; Roligt ↔ Disco styrer stadig pulsens tydelighed.
Lysstyrke sætter maksimum. Uden cover bruges den valgte farve.

Cover modtages fra samme Sendspin-gruppe som musikframes, så der kræves ingen
HA-lampeintegration eller ekstra API-token. Bridge annoncerer nu også artwork-rollen;
genstart add-on efter opdatering, så MA kan genforhandle rollerne. Startupoptionen
`cover_colors: true` bevarer valget efter genstart (ingressændringer er midlertidige).

## Bas og synkronisering · 0.1.9

Den lydløse Sendspin-afspiller måler en bas-envelope i 45–160 Hz og nye spektrale
anslag fra PCM-lyden. En kort FFT-analyse bruger højst 2048 mono-samples og
sammenligner frekvensernes vækst med et maksimumfiltreret tidligere spektrum.
Der er ingen lydudgang eller lagring af optagelser. Konfigurationsvalget `sendspin_player`
skal være **true** for PCM-bas. Ingress viser **PCM-bas aktiv**, når målinger bliver
afviklet, og **Spektral slagdetektor** bekræfter den nye PCM-metode. Ellers bruges
spektrum-bas som fallback.

Prøv **Radial Pulse**, Disco **90–100**, hastighed **1×** og følsomhed **1×**.
Hastighed ændrer mønstrenes bevægelse, ikke musikkens tempo. Positiv **Lysforsinkelse**
giver lyset senere; negativ giver det tidligere. Hvis lyset kommer før det basanslag,
du hører fra Sonos, øges værdien fx 50 ms ad gangen. Indstillingen påvirker både
bas- og visualiseringsframes og virker uden genstart. Gem `light_delay_ms` i add-on-
konfigurationen for at bevare den efter genstart.

Konstant bas giver ikke nødvendigvis tydelige pulser. Dette er basanslag, ikke
perfekt adskillelse af stortromme fra basguitar eller en konstrueret beat-clock.

## Kort måling (0.1.8)

Åbn betjeningssiden og find **Kort måling**. Start en 60-sekunders måling,
mens det problematiske nummer spiller. Optag samtidig Flexen med mobilens
kamera og lyd; hold telefonen stille og undgå helt hvid/overbelyst LED-stribe.
Tryk **Stop måling**, eller vent til den stopper automatisk. Tryk derefter
**Hent måling · JSON**. Ingen bærbar eller mikrofon på HA-maskinen er nødvendig
for denne fremgangsmåde. Optagelsen bliver ikke automatisk sammenkoblet med JSON-filen.

Målingen indeholder afledte niveauer og tidsstempler, ikke selve lyden.
`bass` viser RMS, baseline og hit-beslutning. Fra 0.1.9 viser `detector` den
anvendte metode og `onset` fire værdier: bas-flux, anslags-flux, anslagets andel
af den nye spektrale energi og bassens andel af den aktuelle spektrale energi.
`onset_threshold` er den adaptive tærskel for bas-flux. `spectrum` viser serverens
visualiseringsdata. `schedule` viser tid til planlagt afspilning og om en
ramme afvises, fx fordi negativ lysforsinkelse gør den for gammel ved ankomst.
`led` viser puls, lydkilde, lysstyrke før Twinklys globale dæmpning og tid brugt
på afsendelsen. `t_ms` er tid fra målingens start på add-on'ens monotone ur.
En `led`-hændelse betyder afsluttet afsendelse, ikke bekræftet fysisk lys.

Målingen er slået fra som standard, stopper efter 60 sekunder eller 12.000
hændelser og gemmes kun i hukommelsen indtil ny måling eller genstart.
Automatisk kalibrering med telefonens mikrofon/kamera er ikke implementeret.
En mikrofon kan måle den hørbare musik; kamera eller lyssensor er nødvendigt
for også at måle det fysiske lys.

PCM-detektoren i 0.1.9 er en let tilpasning af principperne i
[SuperFlux](https://librosa.org/doc/0.11.0/auto_examples/plot_superflux.html)
og [forskningsartiklen](https://www.dafx.de/paper-archive/2013/papers/09.dafx2013_submission_12.pdf).
Det er vores basfokuserede variant med lineære FFT-bins og 20 ms hop, ikke
Librosas fulde SuperFlux-implementering. NumPy leverer FFT-beregningen; hele
Librosa/Aubio/Essentia-pakken installeres ikke. Maximum-filteret dæmper små
frekvensbevægelser, og en samtidig skarp anslagskomponent, stigende basenergi
og en adaptiv tærskel mindsker falske pulser fra vedvarende toner.

Der er ingen forudbestemt BPM, og musik uden skarpe basanslag kan derfor give
færre pulser ved høj Disco. Basguitar med skarpe anslag kan stadig registreres;
metoden isolerer ikke en stortrommestemme. De automatiske audio-tests bruger
syntetiske signaler med forskellige frekvenser, niveauer og tempi. Virkelig musik
og fysisk Sonos/Flex-forsinkelse skal fortsat afprøves. Analysevinduet kan give
nogle få tiere millisekunders detektionsforsinkelse; lysforsinkelsen ændres ikke
automatisk. Mirror Spectrum beholder sine farver og frekvensbevægelser; Radial
Pulse er lettest at bruge til at kontrollere selve pulserne.
