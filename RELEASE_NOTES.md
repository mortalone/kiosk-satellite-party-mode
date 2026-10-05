# Party Mode 0.1.1

- Fix installation error: `Unexpected or duplicate ZIP entry: THIRD_PARTY_NOTICES.md`.
- Include all QR library notices in the accepted `LICENSE` file rather than an unsupported extra root entry.
- Verify the actual built ZIP with Kiosk Satellite's pinned SDK 1 `PluginPackage` and `PluginManifest` before release. Check extraction, DEX, manifest, checksum and bundled license. Reproduce the original rejection as a regression check.
- Preserve independent Party visibility, Home Assistant actions, screen controls, queue, guest QR and visual effects.

Retry installation using https://github.com/mortalone/kiosk-satellite-party-mode. Use Now Playing 0.2.4, Spectrum Visualizer 0.2.11 and Quick Actions 0.2.6.
