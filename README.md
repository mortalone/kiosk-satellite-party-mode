# Party Mode for Kiosk Satellite

A standalone full-screen plugin with its own settings, Home Assistant actions and visibility. Party does not depend on Now Playing being enabled or its visibility, nor on an active screensaver. It renders the selected Music Assistant speaker group's queue and optional guest QR over native audio effects.

## Setup

1. Connect Music Assistant in Kiosk Satellite so its URL and token are available.
2. Select the group's **Music Assistant HA media_player** in **Speaker / højttaler**. Party follows that entity's `active_queue`; it does not select an output or change speaker volume.
3. Enable Party Mode and use **Start Party Mode**. Alternatively enable **Start automatically when visibility allows** and configure Party's own visibility. Automatic start defaults off so installing the plugin does not immediately cover the settings screen.
4. **Menu and Close buttons** defaults to **Menu only**, so the Close icon stays hidden. Choose Menu and Close, Close only, or Hidden if desired. Search and favorites have their own permissions. **Volume controls** selects Off, compact −/+ Buttons (default), or a slim Slider. **Show playback controls** independently enables Play/Pause and Stop. HA actions work in all modes.
5. For audio effects, enable Spectrum Visualizer **0.2.11+** as the audio analyzer. Its existing source/capture settings determine audio input. Party owns its effect, gain and FPS; it hides the normal spectrum overlay while Party is displayed. Choosing `off` requires no audio capture.

The bottom buttons operate the selected MA queue. The volume controls use MA group volume for that queue’s speaker/group, never Kiosk’s master volume. It shows the actual MA group volume and send a change with each −/+ tap (3 percentage points), or when the slider is released. Missing queue/connection or unknown volume disables the affected control. The MA token needs queue-control and player read/control permissions. Volume and visualization gain remain separate.

## Independent visibility

Use the three ordinary controls: entity, condition and value. These apply to manual and automatic Party start. Supported conditions include active/inactive, state equality, numeric bounds and time windows, including overnight. Unavailable entity states and invalid values keep Party hidden. **Only while playing** optionally adds the selected speaker's playback state; **Allow while paused** controls paused playback.

Stop prevents automatic reopening until visibility/playback eligibility closes and opens again, or Start is explicitly called. Leaving Kiosk closes Party. Rotation recreates its view. The regular Now Playing companion hides while Party is active. Quick Actions hides by default and can be enabled above Party; companions retain their own visibility afterward.

## Queue and guest access

Party gets the current track and upcoming tracks directly from the selected MA queue, with cover art and progress. It needs no Next track entity or Show next track setting. The two track counts configure the queue window. The existing layout actions switch between that list and a smaller current-song card.

Select the same explicit group in Music Assistant's **Party Player** and enable **Guest Access**. Party uses the actual join URL supplied by MA and generates its QR locally. The QR is hidden if the Party queue differs from the selected group or guest access cannot be confirmed. Requests use MA's guest interface and queue rules.

Guest-enable/disable actions write only `enable_guest_access` on the single enabled Party provider whose explicit player matches this queue. The configured token needs provider-settings access. Ambiguous, Auto and unmatched providers are left untouched. Hiding the QR does not disable MA guest access.

## Actions

- Start / Stop Party Mode.
- Visualization: None, Neon Spectrum, Mirror Spectrum, Radial Pulse, Waveform, Star Particles, Neon Tunnel.
- Screen controls: Settings and Close / Close only / Hidden.
- Layout: full queue / current song only.
- Show/hide volume and show/hide playback controls: two independent saved toggle actions. The screen menu also has separate checkboxes. These visibility actions do not change playback or volume.
- Guest QR: follow Music Assistant / hide.
- Guests: enable / disable Music Assistant guest access.

Presentation choices made in actions or the screen menu persist across restart. Changing the corresponding plugin setting replaces the saved action choice. Gain adjusts visual strength, never audio volume. Animated input is labeled as demo. Audio-dependent output still depends on what Android's selected capture method supplies.

## Install and build

Add this full repository URL in Kiosk Satellite's Plugin Manager:

https://github.com/mortalone/kiosk-satellite-party-mode

Use Party Mode 0.1.6+, Now Playing 0.2.4+, Spectrum Visualizer 0.2.11+ and Quick Actions 0.2.7+. The companions retain their own visibility when Party closes. Update Now Playing to remove the old full-screen Party actions, then enable this plugin and select the intended MA speaker group.

```sh
python3 tools/build.py --android-platform 35
```

CI also extracts the actual release ZIP using Kiosk Satellite’s pinned SDK 1 installer and verifies its manifest, checksum and bundled QR license before publication. It reproduces the rejected extra root file as a regression check. CI compiles Android Java, D8 and the package, then tests queue selection, guest matching, QR decoding, frame bounds, start/stop and visibility. Real kiosk drawing, Home Assistant action discovery and live MA guest access require device verification.

## Jukebox and guest lockdown (0.1.3)

- **Allow music search** adds a Search button independently of Menu/Close. Search uses Music Assistant track search (up to 20 results), then offers **Add to queue** or **Play now** on the selected MA queue.
- **Allow queue tracks to play on tap** is off by default. Turn it on to start previous/upcoming songs immediately by stable queue item ID. Current song is not a jump target. Queue actions require a fresh queue snapshot.
- **Tracks before current / Tracks after current** each accept 0–10. Lists scroll instead of shrinking text. Set both to 0 for current song only. Existing HA full-queue/current-song actions still work.
- **Show Quick Actions above Party** is off by default; requires Quick Actions 0.2.7+. Its action-specific visibility rules remain active. This switch permits the rail during Party even without a screensaver.
- EQ choices are off by default; select **EQ** or **Playlists and EQ** in **Playlist and EQ controls**. Enable it with Menu only or Menu and Close for Party Punch / Restore original EQ.
- For a locked guest screen: hide Menu/Close, search, queue tapping, volume, playback buttons, EQ, and Quick Actions independently. HA start/stop and visibility remain available.
- The old Show full queue backend switch is replaced by the two track counts. Saved current-song/full-queue actions remain supported. MA guest setup instructions appear in plugin status, never over the music.

### Party Punch: a starting point for Sonos Play:5 Gen 1

The preset uses MA DSP, not a visualization effect or kiosk volume: input −5 dB, 60 Hz low shelf +1.5 dB/Q 0.7, 95 Hz peak +2.5 dB/Q 0.9, 220 Hz peak −1.5 dB/Q 0.8, 7 kHz peak +0.5 dB/Q 0.7. Output gain is 0. The input reduction leaves headroom for bass boost. This is an ear-tuning starting point for warmth/punch, not a measured JBL/Harman Kardon match or a replacement for a subwoofer.

MA requires an **admin token** to save DSP. Individual DSP is supported for Sonos in **Universal groups**, and for standalone Sonos. Native Sonos groups do not support MA's individual DSP; the plugin reports this instead of applying a misleading preset. Only available direct Sonos members of the selected Universal group are adjusted; Sendspin/kiosk members are skipped. Each target's complete original DSP configuration is saved before the first change and **Restore original EQ** restores it exactly. EQ persists after closing Party until restored. A partial change is reported; use Restore original EQ if one member failed. Tune further in MA's player DSP settings after listening in your room.

### Rendering

The queue, artwork, and QR code use a retained native drawing layer. Audio updates and animation share one bounded frame scheduler, while playback progress runs at 1 Hz without an effect. Effects use up to 48 spectrum bars, 96 waveform samples, 48 particles, and 10 tunnel rings. Paused playback has no continuous animation loop. The existing 10/20/30 FPS choice remains available; start with 10 FPS on a slower Pi. Performance must be checked on the actual kiosk device.

## Modern panels, lyrics and event playlists (0.1.5)

Search uses a drawn magnifying-glass icon, a dark rounded field, cover thumbnails and readable title/artist rows. Settings uses the same dark native sheet instead of the old platform popup. Previous/upcoming cards progressively narrow with their distance from the current song.

**Adding a track:** choose Now (0), Next (1), No. 3, another position 0–100, or End (blank). The last choice is remembered. Positive positions are relative to the currently playing song. If the queue is shorter, the track goes at the end. For exact placement the plugin appends one track, identifies its new stable queue ID, verifies the queue's tail/current song, then moves only that item. Shuffle, buffered destinations and concurrent edits prevent an exact move; a track already added remains at the end and a message explains this. Positions never replace the entire queue. Favorite playlist activation separately offers **Start playlist · replace queue** or **Add whole playlist at end**.

**Favorite playlists:** select Playlists or Playlists and EQ in **Playlist and EQ controls**. A playlist icon opens an animated side panel; the panel is closed by default. It reads up to 200 available favorite library playlists from MA each time it opens. Mark/unmark favorites in MA to change the selection without editing this plugin.

**Lyrics:** choose `lyrics` in Visualization or **Lyrics · syng med** in the on-screen settings. MA's `lrc_lyrics` follows the current queue's timeline and highlights/scrolls the current line. Plain lyrics can be read manually; no timings are invented. A subdued spectrum plays underneath when Visualizer is available; text also works without the audio analyzer. Missing lyrics do not trigger direct third-party requests. Enable/check MA's lyrics metadata providers (e.g. LRCLIB) and refresh the track's metadata in MA if necessary. First metadata lookup can be delayed. Guest QR is hidden in lyrics layout to preserve text space.

**Graphics:** the queue/QR uses a separate native View, so Android can retain its display list while the animated background updates. The full-screen CPU bitmap cache is removed. The background is preblended, spectrum/waveform buffers are reused, colors/radial directions are precalculated, and frames align with Android's animation scheduling. `10 FPS Eco` / `20 FPS Eco` use 32 bands, 64 waveform samples, 28 particles or 7 rings. Settings reports whether the actual drawing Canvas is hardware accelerated. The plugin follows the host's graphics pipeline; it cannot supply a missing Pi Android GPU driver. Emulator smoke tests validate native main/search/placement/favorites/settings/lyrics panels with mock MA, not actual Pi frame rates or live MA playback.

Backend compatibility: the original All controls choice migrates to Menu only to hide Close by default. Existing HA controlsAll explicitly selects Menu and Close. Volume visibility actions remain independent of its Buttons/Slider style. Playlist/EQ access shares one select with all four combinations to stay within Kiosk SDK 1's 20-setting limit.

### Updating from 0.1.3 (0.1.6)

0.1.6 accepts the saved `All controls` choice during Kiosk's pre-load settings validation, then treats it as `Menu only` to hide Close. This fixes `Unknown selection option` when updating directly from 0.1.3. The installer regression check now exercises retained settings from the original 0.1.3 manifest and every old select option, not only a fresh installation.

### On-demand lyrics (0.1.7)

When neither the queue nor full track metadata contains lyrics, Party now calls MA's `metadata/get_track_lyrics` with the full track, matching MA's own Now Playing screen. This supports lyrics which the metadata provider returns on demand without storing them on the track. The existing MA token needs library-read permission. Android regression checks deliberately omit stored lyrics and require a successful on-demand lookup before passing.

## Twinkly companion add-on

This repository also hosts [Twinkly Bridge](twinkly_bridge/README.md), a Home Assistant
add-on with isolated xled/xled_plus libraries, an ingress control panel and individual
LED test patterns. Add this repository URL in the Home Assistant add-on store to
install it. See [configuration and installation](twinkly_bridge/DOCS.md). Version 0.1.1 connects directly to Music Assistant through Sendspin and includes
six Party Mode inspired LED patterns. No Kiosk audio relay is needed.
