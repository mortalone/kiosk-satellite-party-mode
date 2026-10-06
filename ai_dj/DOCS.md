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
   ikke HA's `media_player.…` entity-id. Du skal ikke oprette en ny Pi/Twinkly-gruppe.
5. Vælg AI-motor, start add-on og åbn dens ingress-side.

## AI-motor

**HA AI Task**: `ai_engine: ha_task`. Udfyld `ai_task_entity`, fx den Gemini-entity,
som du allerede bruger til “kald på”. Tomt felt bruger HA's standard AI Task.
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

Opdatér **Party Mode til 0.1.9**. I Party-menuen → **AI DJ · opsæt adresse** indsættes:

`http://192.168.0.18:8101/#token=DIT_API_TOKEN`

Tryk **Gem og åbn AI DJ**. Derefter åbner **DJ**-knappen øverst den samme side.
Aktivér **Gæste-QR · AI DJ i stedet for MA**, hvis Party-QR'en skal føre gæsterne til
DJ'en. Det er et separat, frivilligt DJ-gæstelink; MA's eget gæstelink er fortsat
standard. “Vis gæste-QR” skal også være aktiveret. QR'en deler DJ-adgangen til den
faste gruppe, så skift tokenet for at tilbagekalde tidligere DJ-gæstelinks. Det
følger ikke automatisk MA's “disable guest access”.

## Similarity

I Party-menuen: **Vis lignende-numre-knapper**. Søgeresultater får en **≈**-knap,
som viser en liste med lignende numre og de sædvanlige køvalg. Menuen har også
**≈ Lignende det aktuelle nummer**. MA kan bruge musiktjenesternes egne anbefalinger;
Sonic Similarity er fallback til understøttede, analyserede biblioteksnumre.

## Lovelace og API

Ingress kan åbnes fra HA's sidebar. På et lokalt HTTP-dashboard kan samme DJ-side
indlejres i et `iframe`-kort med URL'en ovenfor. Et HTTPS-dashboard kræver en HTTPS-
adresse til DJ-siden for at undgå browserens blokering af HTTP-indhold.

Automations kan kalde API'en med header `Authorization: Bearer DIT_API_TOKEN`:

1. `POST /api/suggest` med `{"prompt":"blandet rengøringsmusik","count":12}` → job-id.
2. `GET /api/jobs/<id>` indtil `state` er `ready` eller `error`.
3. `POST /api/queue` med `{"id":"…","option":"next","indices":[0,1,2]}`.

`add` = sidst i køen, `next` = efter den aktuelle sang, `play` = afspil nu. Ingen
forespørgsel kan vælge en anden gruppe eller indsende vilkårlige track-URI'er. Et
forslag udløber efter 30 minutter og kan kun tilføjes én gang. Google-højttalernes
frie tale-input er endnu ikke koblet på; API'en er den fælles indgang til dette.
