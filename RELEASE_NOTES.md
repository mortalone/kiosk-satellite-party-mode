Party Mode 0.1.7

- Fetch missing lyrics with metadata/get_track_lyrics, the same on-demand API used by Music Assistant's Now Playing screen.
- Decode MA's [plain, synchronized] lyrics response, including null values, and allow slower provider lookups without changing queue/control request timeouts.
- Regression checks cover on-demand response parsing; Android smoke tests now require synchronized text when both queue and full track metadata contain no lyrics.
- Retains the 0.1.6 upgrade fix and all Party UI features.
