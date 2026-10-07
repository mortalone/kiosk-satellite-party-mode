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

Vælg **Guest QR destination** i HA: **Music Assistant** åbner MA's officielle gæsteside; **Party guest page** åbner vores side med Søg, Similar og AI DJ. Den sidste kræver Party AI DJ **0.1.4**, samme kø-id og ovenstående adresse gemt i Party. QR'en indeholder et særskilt gæstetoken, ikke dit host-token. Gæster kan kun tilføje fundne numre sidst i køen. Siden bruger egne søgebegrænsninger, ikke MA's request/boost-regler. Similar kræver Sonic Similarity i MA; AI DJ kræver valgt AI-forbindelse.

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

## Kontinuerlig DJ (0.1.2)

Åbn ingress-siden i HA, skriv dit ønske og vælg **Køvalg**. Tryk **Start kontinuerlig DJ**.
Det valgte køvalg gælder kun første portion. Derefter tilføjes nye portioner **sidst**,
så gæsternes og dine eksisterende køvalg bevares. Vælg **Spil nu** eller **Erstat hele
køen og spil nu**, hvis DJ'en også skal starte musikken. Standardvalget **Tilføj sidst**
starter ikke afspilningen. En kø, der allerede har mange numre foran, fyldes først op,
når den bliver kort. Ved shuffle styrer MA rækkefølgen og kan blande nye numre ind.

DJ'en kontrollerer køen hvert 20. sekund, finder højst 8 numre ad gangen og fylder mod
8 numre foran, når højst 3 er tilbage. AI-forespørgsler startes højst cirka hvert 2.
minut, og kun når der skal fyldes op. Katalogmatches kontrolleres som før. De seneste
500 DJ-numre og den nærmeste eksisterende kø udelukkes; AI får også besked om at variere
kunstnere og vælge nye indspilninger. Modellen kan stadig foreslå for få nye matches.
Ved fejl eller manglende matches vises årsagen, og DJ'en prøver igen efter 2 minutter.
Dette er ikke en garanti for uafbrudt musik ved AI-/MA-nedbrud eller en tom musikkilde.

Den kan køre, mens siden er lukket, indtil **Stop DJ** eller add-on'en genstartes.
Pause/stop af afspilleren suspenderer påfyldning; DJ'en genstarter ikke en manuelt
stoppet afspiller. Når du spiller igen, fortsætter påfyldningen. Stop DJ bevarer de
numre, som allerede er tilføjet, og afviser et AI-resultat, der endnu ikke er indsat.
Efter genstart af add-on'en skal kontinuerlig DJ aktiveres igen.

Kontinuerlig DJ startes og stoppes kun fra HA ingress. Gæster kan fortsat lave og
indsætte almindelige DJ-forslag; gæste-tokenet kan ikke starte en vedvarende DJ eller
ændre AI-indstillinger. Host-API: `GET/POST /api/admin/radio`, POST med
`{"action":"start","prompt":"varieret rolig jazz","option":"add"}` eller
`{"action":"stop"}`. Et nyt musikønske kræver stop og start igen.

## Native MA search switches (0.1.3)

`search_library_entity`, `search_similar_entity` and `search_ai_entity` accept your existing HA `switch` or `input_boolean` entity IDs. Empty means enabled. Configured entities must be on; missing/unavailable entities disable that search mode. These settings are consumed by the native MA Party AI DJ bridge.
