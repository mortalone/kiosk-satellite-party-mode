# Party Guest — selvstændig gæsteside

Party Guest serverer gæstesiden på Home Assistant. **Party AI DJ og Kiosk Satellite behøver ikke være installeret for at åbne siden, søge eller tilføje numre.** Music Assistant skal være tilgængelig. Kiosk kan vise siden som en QR-kode; AI DJ er en valgfri søgemotor.

## Installation

1. Opdatér add-on-repositoryet `https://github.com/mortalone/kiosk-satellite-party-mode` i HA's add-on-butik. Installér **Party Guest** og start den.
2. Angiv `music_assistant_url` og `music_assistant_token` til din officielle MA. Tokenet skal kunne læse musik/kø og tilføje numre.
3. Angiv `queue_id`: MA-køens id eller gruppens HA `media_player.*`. Ved en HA-entity følger siden dens `active_queue`.
4. Angiv `public_url` som `http://192.168.0.18:8102`, eller din egen browsertilgængelige adresse. Port 8102 er mappet som standard. Har du allerede valgt fx 8103, behold den port og din eksisterende `public_url`.
5. Åbn ingress og tryk **Åbn gæstesiden i browseren**. Adressen kan også åbnes direkte: **http://192.168.0.18:8102/guest/**. Den kræver ikke et token fra en QR-kode; serveren opretter en begrænset gæstesession.

## QR i Kiosk Party

Opdatér Party Mode til **0.1.14**. Angiv Party Guest's `api_token` til en tilfældig adgangskode på mindst 24 tegn. Ingress viser derefter **Forbind Kiosk Party** med den særskilte værtsforbindelse.

Gem forbindelsen i Party-menuen → Gæster → **Party Guest · opsæt adresse**:

`http://192.168.0.18:8102/#token=DIT_PARTY_GUEST_API_TOKEN`

Vælg **Guest QR destination → Party guest page**. Party Guest og Kiosk skal pege på samme MA-kø. QR'en indeholder et separat gæstetoken, aldrig værts- eller MA-tokenet. Den tidligere AI DJ-baserede gæsteforbindelse fortsætter som kompatibilitet, indtil denne nye forbindelse gemmes.

## Søgning og adgang

- **Bibliotek:** titel og kunstner i dit MA-bibliotek. Ingen AI.
- **Samme stil:** fritekst gennem Sonic Similarity, som kræver aktiveret free-text search og et analyseret bibliotek i MA. Lignende det aktuelle nummer bruger MA's anbefalinger.
- **AI:** vises kun, hvis den valgfrie AI DJ-forbindelse er tilgængelig og tilladt.

`guest_access` lukker adgang til søgning/kø, inklusive eksisterende sessioner. `guest_access_entity` kan pege på en HA switch/input_boolean; off/unavailable lukker adgang. `search_library_entity`, `search_similar_entity`, `search_current_similar_entity` og `search_ai_entity` styrer søgemåderne på samme måde. Tomme entity-felter betyder tilladt. Kiosk's HA-søgeswitches begrænser også de sessioner, Kiosk opretter.

Alle på netværket, som kan åbne den mappede gæsteadresse, kan få en gæstesession, når gæsteadgang er aktiveret. Gæster kan kun tilføje verificerede søgeresultater til den valgte kø med værtens køplacering. De kan ikke ændre køplaceringen, vælge en anden kø, styre værtsopsætningen eller læse AI-/MA-nøgler. Værten kan vælge sidst, næste, spil straks eller erstat kommende; sidst er standard. Søgning har egne frekvensgrænser og bruger ikke MA Party's request/boost-regler. MA's officielle gæsteside kan fortsat vælges som QR-destination.

## Valgfri AI DJ

Installer Party AI DJ separat og konfigurér dens AI-model. I Party Guest angives:

- `ai_dj_url`: fx `http://192.168.0.18:8101` (uden fragment/token).
- `ai_dj_token`: AI DJ-add-on'ens API-token.

Party Guest bruger kun AI DJ til at hente forslag og resultater. Tilføjelse til køen sker gennem Party Guest's egen, begrænsede gæsteadgang. Hvis AI DJ stoppes eller fjernes, fortsætter Søg og Similar; AI-fanen skjules ved næste konfigurationsopdatering. Ingen AI Task eller AI-nøgle kræves i Party Guest.

## Lignende ud fra et nummer

Knappen **≈** til højre ved hvert søgeresultat og nummer i køen finder musik, der ligner netop dét nummer. `search_current_similar_entity` styrer disse knapper; `search_similar_entity` styrer kun tekstfeltet under Samme stil. Du kan altså have knapperne slået til og tekstsøgningen slået fra. Manglende coverbilleder vises med et musikikon.

## Kø og automatisk fortsættelse

Party Guest 0.2.0 ingress samler **Gæsternes musikønsker → Placering i køen** og **Automatisk fortsættelse**. Gæstesidens tekst følger den aktuelle placering. Disse indstillinger er uafhængige af AI DJ ingress' køvalg til manuelle AI-forslag.

Vælg metode og **1–5 kommende numre** (standard 1):

- **Mine favoritnumre:** blandede favoritmarkerede numre fra MA-biblioteket, ikke favorit-playlister. Starter en ny runde, når puljens numre har spillet; undgår det aktuelle og kommende numre.
- **Lignende den aktuelle musik · MA:** MA's similar-track-anbefalinger fra de tilgængelige musikkilder. Spotify kan indgå, hvis MA's provider understøtter det; ingen særskilt Spotify-forbindelse kræves her.
- **AI-musikønske:** bruger tekstønsket og den valgfrie AI DJ-forbindelse. AI DJ 0.1.6 modtager også nylige og kølagte numre, som skal undgås.

Start selv musikken. Party forbereder forslag, mens den sidste del af køen spiller, og fylder kun det antal kommende pladser, du har valgt. Nye gæsteønsker stopper yderligere påfyldning, indtil køen bliver kort igen. Allerede tilføjede automatiske numre bliver i køen; med 1 venter et nyt ønske kun bag det ene automatiske nummer. Værtens valgte køplacering gælder stadig. Pause/stop genstarter ikke afspilleren. Til/fra begynder heller ikke selv afspilningen.

Andre valg gemmes efter genstart, men automatisk fortsættelse starter som slået fra. En tilknyttet HA-switch kan aktivere den igen. Afspilleren skal stadig spille.

## HA-styring

Kiosk Party 0.1.14 opretter disse HA-entiteter, når den særskilte Party Guest-værtsforbindelse er gemt, og MA-køen matcher:

- **Party: automatisk fortsættelse** — switch.
- **Party: automatisk musik fra** — select: Favoritnumre, Samme stil (MA), AI-musikønske.
- **Party: antal automatiske numre** — select: 1–5.
- **Party: gæsternes køplacering** — select: Sidst i køen, Som næste, Spil straks, Erstat kommende.

Opdatering fra ingress aflæses ca. hvert 10. sekund. HA-styringen virker også med Party-skærmen lukket; Kiosk-pluginet skal køre. AI-tekstønsket angives i Party Guest ingress.

Uden Kiosk kan eksisterende HA-hjælpere angives i addon-konfigurationen: `continuous_entity` (switch/input_boolean), `auto_method_entity` (select/input_select med `favorites`, `similar`, `ai`), `auto_count_entity` (select/input_select/input_number/number med 1–5), `queue_option_entity` (select/input_select med `add`, `next`, `play`, `replace_next`). Tilknyttede hjælpere har forrang over ingress' gemte værdier; ændr dem i HA. Utilgængelige hjælpere slår automatisk fortsættelse fra.
