# Party Mode 0.1.0

- Standalone plugin identity, own MA speaker selection, independent visibility and Home Assistant Start/Stop actions.
- Separate full-screen view inside Kiosk, independent of Now Playing and screensaver visibility.
- Clearly labeled top Settings menu; choose all screen controls, Close only, or hidden, also through saved actions.
- Six native visualizations plus None, independent gain/FPS; uses one analyzer from Spectrum Visualizer 0.2.11+.
- Current song and upcoming queue from the selected MA entity's active queue; no manual next-track entity or toggle.
- MA guest QR, local QR generation, queue matching and scoped guest-access actions.
- Companions yield during Party: Now Playing 0.2.4 and Quick Actions 0.2.6.

Install with https://github.com/mortalone/kiosk-satellite-party-mode in Kiosk Satellite. Update Now Playing to 0.2.4, Spectrum Visualizer to 0.2.11 and Quick Actions to 0.2.6.

Android build and automated tests verify packaging and queue, guest, QR, signal and visibility logic. Real-device rendering and live MA access require kiosk verification.
