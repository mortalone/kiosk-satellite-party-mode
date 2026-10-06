# Twinkly Bridge

Home Assistant add-on for local Twinkly/Flex control through xled and xled_plus.
Includes an ingress control panel, individual LED test patterns and an authenticated
receiver for audio spectrum data. Connect directly to Music Assistant's Sendspin
server for timestamped spectrum, loudness and peak data. The client advertises
a silent PCM player and a visualizer role by default, allowing a universal group
to treat it as an audio destination. Received PCM is analyzed into timestamped
45–160 Hz bass envelopes and short spectral attack features, then discarded;
there is no audio output or microphone. Set `sendspin_player`
to false to restore visualizer-only mode.
Six LED patterns are inspired by Party Mode's visualizations. A live Calm ↔ Disco
slider adjusts response speed and music-driven pulse contrast independently of
the brightness limit.

Individual LED chase output was confirmed on the user's Flex with 0.1.0.
Direct Sendspin visualization was confirmed with 0.1.1 through the browser and Pi
players. The user confirmed 0.1.3 works with the mixed Pi/Sonos group.
Version 0.1.7 keeps bass pulses active when spectrum frames stop and preserves
short attacks between LED refreshes. Physical speaker/Flex synchronization still
requires testing. Version 0.1.9 adds a lightweight maximum-filter spectral-flux
detector inspired by SuperFlux, with adaptive thresholds and a coincident bass/
broadband-attack gate. It suppresses tested beating tones, vibrato and tremolo
without generating a synthetic beat clock. This is not isolated kick recognition;
sharp bass-instrument attacks can still trigger. Physical timing and mixed music
still require testing on the Flex.

Dependencies are pinned and installed when the container is built, never in
Home Assistant or Pyscript. No Home Assistant configuration directories, host
networking, Supervisor privileges or hardware devices are requested.

See [installation and configuration](DOCS.md).
