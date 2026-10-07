# Party AI DJ · opsætning

Denne add-on sammensætter en rigtig liste ud fra fx “blandet søndagsrengøringsmusik”,
“rolig jazz med saxofon” eller “varieret musik fra 1997”. AI foreslår kunstner/titel/
oprindeligt udgivelsesår. Music Assistant søger i dine tilsluttede kilder, og kun
sikre kunstner/titel-matches kommer på forhåndsvisningen. Resten springes over.

Numrene behøver ikke være lydanalyseret. Similarity er en separat funktion.
AI kan stadig tage fejl om årstal, genre og instrumenter. Et årstal i ønsket filtrerer
AI-forslagene, men årstallet vises som **AI-årstal**, fordi originalt udgivelsesår
ikke altid kan bekræftes i katalogets metadata (fx genudgivelser). Intet afspilles,
før du vælger numrene og trykker tilføj. Den første version tillader op til 20 numre,
højst to pr. kunstner, og undersøger reserveforslag, hvis numre mangler.

## Installér

1. Opdatér repository-oplysninger i HA's add-on-butik. Installér **Party AI DJ** fra
   samme repository som Twinkly Bridge. Den erstatter ikke Music Assistant.
2. `music_assistant_url`: din MA-server, fx `http://192.168.0.18:8095`.
3. `music_assistant_token`: et MA-token med bibliotekssøgning og afspiller-/køstyring.
   Det er **ikke** HA-tokenet. Det opbevares i add-on-konfigurationen og sendes aldrig
   til gæste- eller Party-skærmen.
4. `queue_id`: MA's id for din **eksisterende universelle gruppe**. Se gruppens MA
   media_player-attribut `active_queue` i HA Udviklerværktøjer → Tilstande. Brug id'et,
   eller angiv gruppens HA `media_player.…` entity-id; DJ'en læser så `active_queue` ved køvalg. Du skal ikke oprette en ny Pi/Twinkly-gruppe.
5. Vælg AI-motor, start add-on og åbn dens ingress-side.

## AI-motor

**HA AI Task**: `ai_engine: ha_task`. Udfyld `ai_task_entity`, fx den Gemini-entity,
som du allerede bruger til “kald på”. Du kan i stedet åbne ingress-siden, folde **AI i Home Assistant** ud og vælge modellen i listen. Valget gemmes i add-on'ens data og gælder også gæster. Det tilsidesætter `ai_task_entity` indtil du vælger en anden model i ingress. Et tomt felt kræver nu et eksplicit valg; DJ'en kalder ikke en ukendt HA-standard.
Add-on'en bruger Supervisors adgang til HA, så der skal ikke indtastes et HA-token.

**OpenAI Compatible**: `ai_engine: openai_compatible`. Udfyld:

- `openai_base_url`, fx `https://openrouter.ai/api/v1` (uden `/chat/completions`).
- `openai_model`: modellens præcise API-id fra din udbyder.
- `openai_api_key`: udbyderens API-nøgle.

Music Assistants OpenAI Compatible-plugin bruger samme type API. Den offentlige MA
API udstiller ikke et generisk kald til pluginets `ai_query`, så denne add-on har sin
egen motoropsætning; den læser ikke eller kopierer MA's gemte hemmeligheder.
Udbyderens almindelige modelpriser og begrænsninger gælder. Ingen indbygget websøgning
eller aktuelle hitliste-opslag er aktiveret; forslagene bygger på modellens viden.

## Party-skærm og gæste-QR

For at åbne DJ'en fra Pi eller telefonen skal du vælge en lokal værtsport (fx 8101)
for add-on'ens `8101/tcp`. Udfyld `api_token` med en tilfældig adgangskode på mindst
24 tegn. Den giver kun adgang til DJ-forespørgsler, resultater og køvalg for den
konfigurerede gruppe. Lad porten være umappet, hvis ingress er tilstrækkelig.

Opdatér **Party Mode til 0.1.12**. I Party-menuen → **AI DJ · opsæt adresse** indsættes:

`http://192.168.0.18:8101/#token=DIT_API_TOKEN`

Tryk **Gem og åbn AI DJ**. Forstørrelsesglasset samler nu **Søg**, **Similar** og **AI DJ** i samme panel og søgefelt. AI-resultater vises med coverbilleder og de sædvanlige valg af køplacering. Adressen vises kun i forbindelsesopsætningen.

HA-switches **Search: Library**, **Search: Similarity**, **Search: AI DJ** og **Similar to current track** gemmer, hvilke muligheder der vises. Den eksisterende `Allow music search` er fortsat hovedtilladelsen.

Vælg **Guest QR destination** i HA: **Music Assistant** åbner MA's officielle gæsteside; **Party guest page** kan nu bruge den selvstændige **[Party Guest](../party_guest/DOCS.md)** add-on med Søg og Similar uden AI DJ. Party Guest har egen ingress med browserlink og egen Kiosk-forbindelse på port 8102. AI DJ tilsluttes valgfrit til Party Guest med `ai_dj_url` og `ai_dj_token`. Den tidligere indbyggede gæsteside på port 8101 fungerer fortsat som kompatibilitet.

Tidligere direkte add-on-links med `#token=...` virker stadig. De er separate fra MA's Guest-switch; skift add-on-tokenet for at tilbagekalde dem.

## Similarity

Vælg **Similar** under forstørrelsesglasset. **≈ Lignende det aktuelle nummer** bruger nummeret, der spiller nu. Med **Similar to current track** aktiveret får søgeresultater også en **≈**-knap. MA kan bruge musiktjenesternes anbefalinger; fritekstsøgning under Similar kræver Sonic Similarity og analyserede biblioteksnumre.

## Lovelace og API

Ingress kan åbnes fra HA's sidebar. På et lokalt HTTP-dashboard kan samme DJ-side
indlejres i et `iframe`-kort med URL'en ovenfor. Et HTTPS-dashboard kræver en HTTPS-
adresse til DJ-siden for at undgå browserens blokering af HTTP-indhold.

Automations kan kalde API'en med header `Authorization: Bearer DIT_API_TOKEN`:

1. `POST /api/suggest` med `{"prompt":"blandet rengøringsmusik","count":12}` → job-id.
2. `GET /api/jobs/<id>` indtil `state` er `ready` eller `error`.
3. `POST /api/queue` med `{"id":"…","option":"next","indices":[0,1,2]}`.

`add` = sidst i køen uden at starte afspilning, `next` = som næste, `play` = afspil nu og behold resten, `replace_next` = erstat kommende numre og behold den aktuelle sang, `replace` = erstat hele køen og spil nu. MA kan bevare en allerede bufferet overgang. `replace` kræver `confirm_replace: true`. Ingen
forespørgsel kan vælge en anden gruppe eller indsende vilkårlige track-URI'er. Et
forslag udløber efter 30 minutter og kan kun tilføjes én gang. Google-højttalernes
frie tale-input er endnu ikke koblet på; API'en er den fælles indgang til dette.

## Automatisk fortsættelse i Party Guest (0.1.6)

Gæsternes køplacering og automatisk fortsættelse styres nu i **[Party Guest 0.2.0](../party_guest/DOCS.md)**. Vælg Favoritnumre, Samme stil via MA eller AI-musikønske, og 1–5 kommende numre (standard 1). Kiosk Party 0.1.14 udstiller til/fra og valg som HA-switch/selects. Bibliotek og Samme stil kræver ingen AI DJ.

AI DJ ingress viser fortsat manuelle forslag med køvalg til de numre, du selv tilføjer fra den side. Det valg ændrer ikke gæsternes placering. Party Guest bruger AI DJ alene som valgfri forslagsmotor.

Den tidligere kontinuerlige DJ-motor bevares som kompatibilitet til eksisterende automationskald. Ingress har ikke længere Start/Stop DJ-knapper. Den gamle ingress-beskyttede API er `GET/POST /api/admin/radio` med `{"action":"start","prompt":"varieret rolig jazz","option":"add"}` eller `{"action":"stop"}`. Den starter som slået fra efter genstart. Brug Party Guest til den nye, fælles Party-styring, og undgå at køre begge påfyldningsmotorer på samme kø.

## Native MA search switches (0.1.3)

`search_library_entity`, `search_similar_entity` and `search_ai_entity` accept your existing HA `switch` or `input_boolean` entity IDs. Empty means enabled. Configured entities must be on; missing/unavailable entities disable that search mode. These settings are consumed by the native MA Party AI DJ bridge.
