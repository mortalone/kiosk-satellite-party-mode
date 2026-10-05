# Twinkly Bridge

Home Assistant add-on for local Twinkly/Flex control through xled and xled_plus.
Includes an ingress control panel, individual LED test patterns and an authenticated
receiver for audio spectrum data. This is an initial hardware-test release: the
Kiosk audio sender is not included yet, and Flex firmware compatibility needs a real-device test.

Dependencies are pinned and installed when the container is built, never in
Home Assistant or Pyscript. No Home Assistant configuration directories, host
networking, Supervisor privileges or hardware devices are requested.

See [installation and configuration](DOCS.md).
