# AI DJ inde i Music Assistant — udviklingsversion

Dette er en rigtig MA plugin-provider og en lille ændring af **MA's eksisterende Party-gæsteside**. Der er ingen ekstra gæsteside. AI-motoren og katalogmatch genbruges fra den allerede fungerende Party AI DJ-add-on.

**Status:** udviklingskode til en tilpasset MA-build. Den dukker ikke automatisk op i en almindelig MA-installation, når HA's add-on-repository opdateres. Den er ikke testet mod Jacobs kørende MA-server. Installér ikke en ekstra MA-server ved siden af den eksisterende for at afprøve den.

## Opbygning

- `provider/` installeres som `music_assistant/providers/ai_dj` i MA-serverens kildekode.
- `frontend.patch` og `frontend/PartyAiSearch.vue` ændrer den eksisterende `PartyGuestView` og genbruger `PartyResultItem` og dens oprindelige request/boost-handler.
- Gæster bruger MA's sædvanlige QR, login og token. Add-on-tokenet bliver på MA-serveren.
- Gæsters AI-adgang kræver MA Party Guest access **og** providerens `Allow guests to use AI DJ`.
- AI-forslag tilføjes enkeltvis gennem `party/add_to_queue`. Der findes ingen AI-genvej til at overskrive køen eller omgå Party's eksisterende handlinger.
- AI-job er bundet til session og Party-kø, udløber efter 30 minutter og begrænses til én forespørgsel pr. session hvert 30. sekund.
- Resultater genindlæses gennem MA og filtreres efter brugerens synlige afspilningskilder.

## Byg fra kildekode

Den fastlåste MA-server kræver Python 3.14.

`upstream.json` fastlåser server- og frontend-revisionerne. `apply.py` afviser andre revisioner og eksisterende AI DJ-filer; det ændrer ikke din HA eller en kørende MA-installation.

```sh
python ma_ai_dj/apply.py --server /sti/til/ma-server --frontend /sti/til/ma-frontend
```

Byg frontend efter MA's officielle vejledning, og medtag dens byggede `music_assistant_frontend`-pakke i den tilpassede server. Kør MA's egne checks før deployment. Dette repository indeholder endnu ikke en færdig HA-installationspakke til den tilpassede MA-server.

I den tilpassede MA vælges **Settings → Plugins → Party AI DJ**. Angiv add-on-adressen, eksempelvis `http://192.168.0.18:8101`, og dens eksisterende `api_token` hver for sig. Brug samme eksisterende MA-server i add-on-konfigurationen. Vælg din eksisterende gruppe i MA's Party-plugin, og aktivér Guest access.

Den almindelige MA gæste-QR åbner derefter samme side med søgemåderne Search, Similar og AI DJ. AI-fanen skjules, hvis broen eller gæsteadgangen ikke er tilgængelig. Den kontinuerlige DJ styres fortsat i add-on'ens værts-ingress.

## Kontrol

```sh
python -m unittest discover -s ma_ai_dj/tests -v
```

Frontendændringerne skal også typekontrolleres og bygges i den fastlåste MA frontend. Backendbroens session-/køisolering og begrænsninger har separate tests; dette erstatter ikke en live test af MA, HA og gæstelogin.
