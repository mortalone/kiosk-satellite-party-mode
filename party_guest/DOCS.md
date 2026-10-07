# Party Guest — selvstændig gæsteside

Party Guest serverer gæstesiden på Home Assistant. **Party AI DJ og Kiosk Satellite behøver ikke være installeret for at åbne siden, søge eller tilføje numre.** Music Assistant skal være tilgængelig. Kiosk kan vise siden som en QR-kode; AI DJ er en valgfri søgemotor.

## Installation

1. Opdatér add-on-repositoryet `https://github.com/mortalone/kiosk-satellite-party-mode` i HA's add-on-butik. Installér **Party Guest** og start den.
2. Angiv `music_assistant_url` og `music_assistant_token` til din officielle MA. Tokenet skal kunne læse musik/kø og tilføje numre.
3. Angiv `queue_id`: MA-køens id eller gruppens HA `media_player.*`. Ved en HA-entity følger siden dens `active_queue`.
4. Angiv `public_url` som `http://192.168.0.18:8102`, eller din egen browsertilgængelige adresse. Port 8102 er mappet som standard.
5. Åbn ingress og tryk **Åbn gæstesiden i browseren**. Adressen kan også åbnes direkte: **http://192.168.0.18:8102/guest/**. Den kræver ikke et token fra en QR-kode; serveren opretter en begrænset gæstesession.

## QR i Kiosk Party

Opdatér Party Mode til **0.1.13**. Angiv Party Guest's `api_token` til en tilfældig adgangskode på mindst 24 tegn. Ingress viser derefter **Forbind Kiosk Party** med den særskilte værtsforbindelse.

Gem forbindelsen i Party-menuen → Gæster → **Party Guest · opsæt adresse**:

`http://192.168.0.18:8102/#token=DIT_PARTY_GUEST_API_TOKEN`

Vælg **Guest QR destination → Party guest page**. Party Guest og Kiosk skal pege på samme MA-kø. QR'en indeholder et separat gæstetoken, aldrig værts- eller MA-tokenet. Den tidligere AI DJ-baserede gæsteforbindelse fortsætter som kompatibilitet, indtil denne nye forbindelse gemmes.

## Søgning og adgang

- **Søg:** titel og kunstner gennem de normale MA-musikkilder.
- **Similar:** fritekst gennem Sonic Similarity, som kræver aktiveret free-text search og et analyseret bibliotek i MA. Lignende det aktuelle nummer bruger MA's anbefalinger.
- **AI DJ:** vises kun, hvis den valgfrie AI DJ-forbindelse er tilgængelig og tilladt.

`guest_access` lukker adgang til søgning/kø, inklusive eksisterende sessioner. `guest_access_entity` kan pege på en HA switch/input_boolean; off/unavailable lukker adgang. `search_library_entity`, `search_similar_entity`, `search_current_similar_entity` og `search_ai_entity` styrer søgemåderne på samme måde. Tomme entity-felter betyder tilladt. Kiosk's HA-søgeswitches begrænser også de sessioner, Kiosk opretter.

Alle på netværket, som kan åbne den mappede gæsteadresse, kan få en gæstesession, når gæsteadgang er aktiveret. Gæster kan kun tilføje verificerede søgeresultater sidst i den valgte kø. De kan ikke vælge en anden kø, erstatte den, styre værtsopsætningen eller læse AI-/MA-nøgler. Søgning har egne frekvensgrænser og bruger ikke MA Party's request/boost-regler. MA's officielle gæsteside kan fortsat vælges som QR-destination.

## Valgfri AI DJ

Installer Party AI DJ separat og konfigurér dens AI-model. I Party Guest angives:

- `ai_dj_url`: fx `http://192.168.0.18:8101` (uden fragment/token).
- `ai_dj_token`: AI DJ-add-on'ens API-token.

Party Guest bruger kun AI DJ til at hente forslag og resultater. Tilføjelse til køen sker gennem Party Guest's egen, begrænsede gæsteadgang. Hvis AI DJ stoppes eller fjernes, fortsætter Søg og Similar; AI-fanen skjules ved næste konfigurationsopdatering. Ingen AI Task eller AI-nøgle kræves i Party Guest.
