# Music Assistant 2.10.5 med Party AI DJ

Denne eksperimentelle HA-installationspakke bygger oven på den officielle MA **2.10.5** og dens frontend **2.17.297**. Den genbruger din eksisterende MA-identitet, brugere, tokens, musikkilder og bibliotek gennem en engangsimport. Den er en **erstatning** for den almindelige MA-add-on. Den separate **Party AI DJ**-add-on er stadig AI-motoren.

## Hvad ændres?

- MA's eksisterende Party-gæsteside får Search, Similar og AI DJ over søgefeltet.
- Party-skærmen på desktop får et forstørrelsesglas, også i fuldskærm. Det åbner den samme søgning og de samme request/boost-handlinger.
- Similar-knappen bruger nummeret i den **konfigurerede Party-kø**. Vælg derfor samme eksisterende gruppe i Party-plugin og på Party-skærmen.
- Gæster bruger MA's eksisterende QR, login og token. Aktiver Guest access i MA's Party-plugin; QR er fortsat MA's eget.
- Forslag matches med kataloget og filtreres til den aktuelle brugers tilgængelige kilder. Add-on-tokenet bliver på serveren.
- Køen ændres kun ved MA's normale request/boost-handlinger. AI kan ikke overskrive den.

## Installation i Home Assistant

Pakken ligger i samme repository:

`https://github.com/mortalone/kiosk-satellite-party-mode`

1. Opdater add-on-repositoryet. Installér **Music Assistant 2.10.5 with Party AI DJ**. Start den ikke endnu. Frontend bygges ved installation; det kan tage tid og kræver ekstra hukommelse.
2. Tag en HA-backup af den eksisterende Music Assistant. Behold den gamle add-on installeret.
3. Stop den gamle MA-add-on, og slå dens automatiske start/watchdog fra under afprøvningen.
4. Kopiér den stoppede MA-servers komplette `/data` til `/share/ma-ai-dj-import`. Det er den gamle MA-add-ons data, **ikke** HA's `/config` eller en krypteret backupfil.
5. Sæt `import_existing_data: true` på den nye MA-pakke, og start den. Den kopierer data til sin egen `/data/ma-data`. Importen ændrer ikke de gamle data og gentages ikke, hvis målserveren allerede er oprettet.
6. Åbn den nye MA fra HA. Den direkte adresse er fortsat `http://192.168.0.18:8095`; HA ingress-menuen har et nyt add-on-id.
7. Under **Settings → Plugins** tilføjes **Party AI DJ** med adressen på den separate AI-motor, fx `http://192.168.0.18:8101`, og dens eksisterende `api_token`. Port 8101 skal være åbnet i AI-motorens netværksindstillinger.
8. Vælg den eksisterende gruppe i Party-plugin, og aktivér Guest access. Åbn Party på desktop eller scan MA's QR med en telefon på samme netværk.

Pakken afviser opstart, hvis MA-port 8094/8095 allerede er i brug, eller hvis de eksisterende data ikke er importeret. Den opretter ikke automatisk en tom ekstra MA-server.

### Kopiering med Docker-adgang på HA-værten

`export-existing-data.sh` kopierer fra den **stoppede** oprindelige container. På Jacobs installation er navnet `addon_d5369777_music_assistant`. Scriptet kræver HA-værtsterminal/Docker-adgang; en almindelig Terminal-add-on giver ikke nødvendigvis den adgang.

```sh
sh export-existing-data.sh addon_d5369777_music_assistant
```

Standarddestinationen på HA-værten er `/mnt/data/supervisor/share/ma-ai-dj-import`, som den nye pakke ser som `/share/ma-ai-dj-import`. Scriptet afviser kørende kilde og eksisterende destination. Importmappen indeholder dine private MA-indstillinger; slet den efter verificeret import og backup af den nye add-on.

### Tilbage til almindelig MA

Stop den tilpassede MA først, og start den gamle add-on igen. De oprindelige data er bevaret. Nye ændringer fra den tilpassede server kopieres ikke automatisk tilbage. Opgradér ikke begge servere og skift frem/tilbage mellem forskellige databaseskemaer.

## Styr søgemåder med HA-switches

Opdater den separate **Party AI DJ** til **0.1.3**. Konfigurer:

```yaml
search_library_entity: switch.din_eksisterende_library_switch
search_similar_entity: switch.din_eksisterende_similarity_switch
search_ai_entity: switch.din_eksisterende_ai_dj_switch
```

Brug de faktiske entity-id'er fra dine eksisterende Kiosk Party-switches. `input_boolean` understøttes også. Tomt felt aktiverer søgemåden som standard. Når et konfigureret entity er off, unavailable eller ikke kan læses, skjules den tilhørende søgemåde. En åben søgning opdateres hvert 15. sekund. AI-switch kontrolleres også på MA-serveren før nye AI-job. Der er ingen lokale switches i MA-søgedialogen.

Providerens **Allow guests to use AI DJ** bestemmer særskilt, om gæster overhovedet må bruge broen. MA's eksisterende Party request/boost-begrænsninger gælder fortsat. Aktiver Guest access også ved afprøvning på desktop; MA's Party-kø-API kræver det i denne version.

## Verifikation og udvikling

`upstream.json` fastlåser både versionsnumre og source-revisioner. `apply.py` kontrollerer begge revisioner og patchen før ændringer. Containeren kontrollerer versionsnumrene på den officielle base før installation af provider og frontend.

```sh
python -m unittest discover -s ma_ai_dj/tests -v
python ma_ai_dj/check_contract.py --server /sti/til/ma-server
python ma_ai_dj/apply.py --server /sti/til/ma-server --frontend /sti/til/ma-frontend
```

CI typekontrollerer og bygger den tilpassede frontend, bygger HA-containeren, importerer provider i den rigtige MA-runtime og kontrollerer importkravet ved opstart. Isolerede tests dækker session/køisolering, begrænsninger og dataimport. Det erstatter ikke test på den kørende HA med Spotify, højttalere og gæstelogin.
