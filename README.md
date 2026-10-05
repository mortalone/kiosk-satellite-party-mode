# Party Mode for Kiosk Satellite

A standalone full-screen plugin with its own settings, Home Assistant actions and visibility. Party does not depend on Now Playing being enabled or its visibility, nor on an active screensaver. It renders the selected Music Assistant speaker group's queue and optional guest QR over native audio effects.

## Setup

1. Connect Music Assistant in Kiosk Satellite so its URL and token are available.
2. Select the group's **Music Assistant HA media_player** in **Speaker / højttaler**. Party follows that entity's `active_queue`; it does not select an output or change speaker volume.
3. Enable Party Mode and use **Start Party Mode**. Alternatively enable **Start automatically when visibility allows** and configure Party's own visibility. Automatic start defaults off so installing the plugin does not immediately cover the settings screen.
4. Choose screen controls: **All controls**, **Close only**, or **Hidden**. All controls shows a labeled **Indstillinger** menu beside Close at the top. Home Assistant actions work in every mode.
5. For audio effects, enable Spectrum Visualizer **0.2.11+** as the audio analyzer. Its existing source/capture settings determine audio input. Party owns its effect, gain and FPS; it hides the normal spectrum overlay while Party is displayed. Choosing `off` requires no audio capture.

## Independent visibility

Use the three ordinary controls: entity, condition and value. These apply to manual and automatic Party start. Supported conditions include active/inactive, state equality, numeric bounds and time windows, including overnight. Unavailable entity states and invalid values keep Party hidden. **Only while playing** optionally adds the selected speaker's playback state; **Allow while paused** controls paused playback.

Stop prevents automatic reopening until visibility/playback eligibility closes and opens again, or Start is explicitly called. Leaving Kiosk closes Party. Rotation recreates its view. The regular Now Playing and Quick Actions companions hide while Party is active and retain their own visibility afterward.

## Queue and guest access

Party gets the current track and upcoming tracks directly from the selected MA queue, with cover art and progress. It needs no Next track entity or Show next track setting. **Show full queue** switches between a queue list and a smaller current-song card.

Select the same explicit group in Music Assistant's **Party Player** and enable **Guest Access**. Party uses the actual join URL supplied by MA and generates its QR locally. The QR is hidden if the Party queue differs from the selected group or guest access cannot be confirmed. Requests use MA's guest interface and queue rules.

Guest-enable/disable actions write only `enable_guest_access` on the single enabled Party provider whose explicit player matches this queue. The configured token needs provider-settings access. Ambiguous, Auto and unmatched providers are left untouched. Hiding the QR does not disable MA guest access.

## Actions

- Start / Stop Party Mode.
- Visualization: None, Neon Spectrum, Mirror Spectrum, Radial Pulse, Waveform, Star Particles, Neon Tunnel.
- Screen controls: Settings and Close / Close only / Hidden.
- Layout: full queue / current song only.
- Guest QR: follow Music Assistant / hide.
- Guests: enable / disable Music Assistant guest access.

Presentation choices made in actions or the screen menu persist across restart. Changing the corresponding plugin setting replaces the saved action choice. Gain adjusts visual strength, never audio volume. Animated input is labeled as demo. Audio-dependent output still depends on what Android's selected capture method supplies.

## Install and build

Add this full repository URL in Kiosk Satellite's Plugin Manager:

https://github.com/mortalone/kiosk-satellite-party-mode

Use Party Mode 0.1.1+, Now Playing 0.2.4+, Spectrum Visualizer 0.2.11+ and Quick Actions 0.2.6+. The companions retain their own visibility when Party closes. Update Now Playing to remove the old full-screen Party actions, then enable this plugin and select the intended MA speaker group.

```sh
python3 tools/build.py --android-platform 35
```

CI also extracts the actual release ZIP using Kiosk Satellite’s pinned SDK 1 installer and verifies its manifest, checksum and bundled QR license before publication. It reproduces the rejected extra root file as a regression check. CI compiles Android Java, D8 and the package, then tests queue selection, guest matching, QR decoding, frame bounds, start/stop and visibility. Real kiosk drawing, Home Assistant action discovery and live MA guest access require device verification.
