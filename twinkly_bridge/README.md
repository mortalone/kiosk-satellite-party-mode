# Twinkly Bridge

Home Assistant add-on for local Twinkly/Flex control through xled and xled_plus.
Includes an ingress control panel, individual LED test patterns and an authenticated
receiver for audio spectrum data. Connect directly to Music Assistant's Sendspin
server for timestamped spectrum, loudness and peak data. The client advertises
only a visualizer role; there is no audio output, microphone or local FFT analyzer.
Six LED patterns are inspired by Party Mode's visualizations.

Individual LED chase output was confirmed on the user's Flex with 0.1.0.
0.1.1 fixes stale UI status, dropped rapid changes and realtime mode recovery;
the full update still needs verification with the physical controller.

Dependencies are pinned and installed when the container is built, never in
Home Assistant or Pyscript. No Home Assistant configuration directories, host
networking, Supervisor privileges or hardware devices are requested.

See [installation and configuration](DOCS.md).
