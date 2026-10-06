Den rigtige AI DJ findes nu i [Party AI DJ-add-on](../ai_dj/DOCS.md). Eksemplet nedenfor bruger den tidligere Similarity-søgning.

# AI DJ · første afprøvning

Første version bruger **Music Assistants eksisterende Sonic Similarity-plugin** som
fælles søgemotor. Party Mode har en knap i søgeboksen, der begrænser søgningen til
denne motor. Den almindelige MA-søgning (og dermed MA-siden fra gæste-QR'en) søger
også plugin-providers. QR-link og gæsters MA-rettigheder er uændrede.

Det er stemningsbaserede **forslag**, ikke en DJ der automatisk komponerer en hel
musikalsk aften eller finder nye sange på alle streamingtjenester. Motoren kræver
allerede lydanalyserede numre med CLAP-fingerprints; uden dem er der ingen forslag.
Sonic Analysis' aktuelle analysebegrænsninger kan derfor gøre denne test uegnet
for et bibliotek, der udelukkende kommer fra streaming. Dette skal afklares før en
bredere DJ bygges. Ingen katalogfallback bliver skjult som et AI-resultat.

## Music Assistant og Party-skærmen

1. I MA: opsæt Sonic Analysis og de afhængigheder dens opsætning kræver (Smart Fades),
   og analysér nogle understøttede biblioteksnumre.
2. Indstillinger → Plugins → Sonic Similarity: aktivér **Enable free-text search**
   og genindlæs pluginet. Character-index aktiveres også.
3. Prøv først `calm jazz with prominent saxophone` i MA. Første søgning kan starte
   en modeldownload (~500 MB) og returnere tomt. Vent på indlæsning og prøv igen.
4. I Party Mode: forstørrelsesglas → **AI DJ · søg efter stemning**. Vælg et forslag
   og brug den eksisterende køplacering (0 nu, 1 næste, osv.). Cover og køvalg er
   de samme som ved en normal søgning.

Engelsk anbefales i denne første motor. Der er ingen automatisk dansk oversættelse
på Party-skærmen eller MA's gæsteside. HA-eksemplet nedenfor kan bruge din eksisterende
AI Task til at oversætte et dansk ønske; dette kræver en konfigureret standard-AI-Task.

## Lovelace og automations

`ai_dj.yaml` er en HA **package**. Kopiér til `/config/packages/party_ai_dj.yaml`
og aktivér packages under `homeassistant: packages: !include_dir_named packages`
i din eksisterende HA-konfiguration. Tilføj de to secrets fra filens kommentar,
kontrollér konfigurationen og genstart HA. MA-tokenet skal kunne læse bibliotek
og søge; afspilningen bruger din allerede opsatte Music Assistant-integration.

Indsæt kortet fra `lovelace_ai_dj.yaml` i dashboardets korteditor, og ret afspillerens
entity-id til din eksisterende MA-gruppe. Ingen ny Pi/Twinkly-gruppe er nødvendig.
**add** lægger forslagene sidst i køen; **next** efter den aktuelle sang; **play**
starter forslagene straks. HA-eksemplet tilføjer op til otte forslag ad gangen.

Slå dansk oversættelse til, når en standard AI Task er konfigureret i HA. Kun ønskets
tekst sendes til den valgte AI-motor; musiksøgning og lyd forbliver hos MA. Uden AI
Task skal oversættelse være slukket og en engelsk beskrivelse bruges. Se scriptets
trace ved AI-, token- eller forbindelsesfejl; statusfeltet er ikke en garanti for
at en forespørgsel stadig kører.

En automation kan kalde `script.party_ai_dj` med `request` og `player`; samme indgang
kan senere bruges fra et tale-flow. Google-smarthøjttalernes modtagelse af frie
musikønsker er **ikke implementeret** i dette forsøg. Den brede DJ med dansk på alle
flader og katalogbaseret kuratering kræver en yderligere fælles backend.

Referencer: [Sonic Similarity](https://www.music-assistant.io/plugins/sonic-similarity/),
[HA REST commands](https://www.home-assistant.io/integrations/rest_command/),
[HA AI Task](https://www.home-assistant.io/integrations/ai_task/).
