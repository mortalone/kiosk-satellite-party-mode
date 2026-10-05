# Party Mode 0.1.2

- Add independent Show volume and Show playback controls settings for full-screen Party. Both are enabled by default.
- Add bottom MA group-volume slider and Play/Pause + Stop buttons; independently selectable alongside the existing Settings/Close visibility.
- Add two saved HA toggle actions and two screen-menu checkboxes for their visibility.
- Target only the selected MA queue/group. Volume uses MA group volume rather than Kiosk master volume or visualizer gain.
- Disable unknown/unavailable controls, reject stale queue/volume responses and protect slider releases when the selected queue changes.
- Preserve the corrected ZIP packaging and verify it with the actual Kiosk installer before publication.

Only Party Mode needs updating for this change. Use https://github.com/mortalone/kiosk-satellite-party-mode. Android builds, installer extraction and automated queue/control tests run before release; live MA commands and touch layout require kiosk verification.
