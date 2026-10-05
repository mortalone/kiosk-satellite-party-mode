# Twinkly Bridge

Home Assistant add-on for local Twinkly/Flex control through xled and xled_plus.
Includes an ingress control panel, individual LED test patterns and an authenticated
receiver for audio spectrum data. Connect directly to Music Assistant's Sendspin
server for timestamped spectrum, loudness and peak data. The client advertises
a silent PCM player and a visualizer role by default, allowing a universal group
to treat it as an audio destination. Received audio is counted and discarded;
there is no audio output, microphone or local FFT analyzer. Set `sendspin_player`
to false to restore visualizer-only mode.
Six LED patterns are inspired by Party Mode's visualizations.

Individual LED chase output was confirmed on the user's Flex with 0.1.0.
Direct Sendspin visualization was confirmed with 0.1.1 through the browser and Pi
players. The new silent-player behavior in 0.1.3 passes reference-server tests but
still needs verification with the physical Pi/Sonos universal group.

Dependencies are pinned and installed when the container is built, never in
Home Assistant or Pyscript. No Home Assistant configuration directories, host
networking, Supervisor privileges or hardware devices are requested.

See [installation and configuration](DOCS.md).
