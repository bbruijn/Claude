# Gesprekstool: beheer en advies voor de school

Voor ICT-beheer, schoolleiding en de functionaris gegevensbescherming (FG).
De handleiding voor docenten staat in [README.md](README.md).

## 1. In het kort

De gesprekstool is een gewoon programma op de laptop van de docent. Er is geen server,
geen internetverbinding, geen account en geen abonnement nodig.

| Onderdeel | Wat het doet |
| --- | --- |
| Gesprekstool | het venster: opnemen, verslag tonen en bewerken |
| whisper.cpp | zet de opname om in tekst (spraakmodel, ca. 1,6 GB) |
| llama.cpp | maakt van de tekst een verslag (taalmodel, 2,5 of 7 GB) |

Alle drie zijn open source. De modellen zijn bestanden op de schijf; er wordt niets
naar een dienst buiten de laptop gestuurd.

## 2. Wat is er minimaal nodig

### Per laptop

| | Minimaal | Aanbevolen |
| --- | --- | --- |
| Mac | Apple Silicon (M1 of nieuwer), macOS 13.3 | idem, 16 GB werkgeheugen |
| Windows | Windows 10/11 (64 bit), processor met AVX2 (Intel Core 4e generatie of AMD Ryzen, of nieuwer) | recente Core i5/Ryzen 5 of beter |
| Werkgeheugen | 8 GB (met het kleine taalmodel) | 16 GB |
| Vrije schijfruimte | 6 GB | 12 GB |
| Microfoon | ingebouwde microfoon | USB-tafelmicrofoon bij gesprekken met drie of meer mensen |
| Schijfversleuteling | FileVault (Mac) of BitLocker (Windows) aan | idem |
| Stroom | - | netstroom tijdens het maken van het verslag |

Niet geschikt: Chromebooks, iPads, telefoons, Intel-Macs, Windows op ARM en laptops met
4 GB werkgeheugen. Daarvoor bestaat geen pakket of ze zijn te licht voor lokale AI.

### Voor de school als geheel

| Wat | Toelichting |
| --- | --- |
| Een beheercomputer met internet | eenmalig, om het pakket en de modellen op te halen (ca. 5 tot 10 GB) |
| Een manier om bestanden uit te rollen | USB-stick volstaat; Jamf of Intune is handiger bij veel laptops |
| Beheerrechten op de laptops | eenmalig, voor de installatie |
| Geen server, geen licenties | de software en de modellen zijn gratis te gebruiken (zie *Licenties*) |
| Afspraken over opnemen en bewaren | zie hoofdstuk 8; betrek de FG voordat de tool in gebruik gaat |

### Welk taalmodel

| Laptop | Advies |
| --- | --- |
| Mac, 16 GB of meer | groot model (`12b`): beste verslagen |
| Mac, 8 GB | klein model (`4b`) |
| Windows, 16 GB, zonder losse videokaart | klein model (`4b`): het grote model werkt, maar is traag |
| Windows, 8 GB | klein model (`4b`) |

Snelheid, als indicatie (niet op schoolapparatuur gemeten): op een Mac met Apple Silicon is
een gesprek van een half uur in enkele minuten verwerkt. Op een Windows-laptop zonder
videokaart kan het verwerken ongeveer zo lang duren als het gesprek zelf. Meet dit in een
proef op de eigen laptops voordat de tool breed wordt ingezet.

## 3. Installeren

### Stap 1: pakket ophalen (met internet)

1. Open de repository op GitHub en ga naar **Actions > Gesprekstool**.
2. Open de laatste geslaagde run en download onder **Artifacts**
   `Gesprekstool-macos-arm64` en/of `Gesprekstool-windows-x64`.
3. Pak het zip-bestand uit. Op de Mac zit er nog een tweede zip in: pak die ook uit.

### Stap 2: modellen ophalen (eenmalig, met internet)

Mac:

```bash
cd Gesprekstool-macos-arm64/beheer
./modellen-ophalen.sh ~/gesprekstool-modellen 12b      # of 4b
```

Windows (PowerShell):

```powershell
cd Gesprekstool-windows-x64\beheer
powershell -ExecutionPolicy Bypass -File modellen-ophalen.ps1 -Doel D:\gesprekstool-modellen -Llm 4b
```

Bewaar de map met modellen (bijvoorbeeld op een USB-stick): dezelfde map is bruikbaar
voor alle laptops. Zet per laptop maar een taalmodel (`.gguf`) neer.

### Stap 3: installeren op een Mac

```bash
cd Gesprekstool-macos-arm64/beheer
sudo ./mac-installeren.sh ~/gesprekstool-modellen
```

Dit zet de app in `/Applications` en de modellen in
`/Library/Application Support/Gesprekstool/models`, en eindigt met een controle.

### Stap 4: installeren op Windows

Start PowerShell als administrator:

```powershell
cd Gesprekstool-windows-x64\beheer
powershell -ExecutionPolicy Bypass -File windows-installeren.ps1 -Modellen D:\gesprekstool-modellen
```

Dit zet het programma in `C:\Program Files\Gesprekstool`, de modellen in
`C:\ProgramData\Gesprekstool\models`, maakt de firewallregel *Gesprekstool netwerkblokkade*
en een snelkoppeling in het startmenu, en eindigt met een controle.

### Stap 5: controleren met de docent

1. Laat de docent inloggen en de Gesprekstool openen.
2. Klik op **Controle**: er mag geen rood kruis staan.
3. Maak een proefopname van een halve minuut. De eerste keer vraagt macOS om toegang tot
   de microfoon: kies *Sta toe*. Op Windows moet *Bureaublad-apps toegang geven tot de
   microfoon* aan staan (Instellingen > Privacy en beveiliging > Microfoon).

### Aandachtspunten bij uitrol op schaal

- **Het programma is niet ondertekend met een certificaat van de school.**
  macOS blokkeert het daarom als het via een browser is gedownload; het installatiescript
  haalt die blokkade weg. Bij uitrol via Jamf of Intune speelt dit niet. Voor structureel
  gebruik: onderteken en notariseer de app met een eigen Apple Developer ID.
- **Windows:** SmartScreen, AppLocker, WDAC of Smart App Control kunnen een niet-ondertekend
  programma tegenhouden. Sta de map `C:\Program Files\Gesprekstool` toe of onderteken de
  programma's met het certificaat van de school.
- **Virusscanner:** sluit de opslagmap met gesprekken uit van het automatisch insturen van
  bestanden naar de leverancier (bijvoorbeeld *Automatic sample submission* in Defender).
- **Bijwerken:** installeer een nieuw pakket over het oude heen. Gesprekken en instellingen
  van gebruikers blijven staan.
- **Verwijderen:** `sudo ./mac-installeren.sh --verwijderen` of
  `windows-installeren.ps1 -Verwijderen`. Gesprekken van gebruikers blijven staan in hun
  eigen map en moeten apart worden gewist.

## 4. Hoe blijven de gegevens op de laptop

### Wat de tool zelf doet

| Maatregel | Mac | Windows |
| --- | --- | --- |
| Hulpprogramma's kunnen geen netwerk gebruiken | afgedwongen door macOS (sandbox); werkt dit niet, dan weigert de tool te verwerken | firewallregel uit het installatiescript; de controle meldt of die er is |
| Taalmodel alleen bereikbaar binnen de laptop (`127.0.0.1`) | ja | ja |
| Taalmodel-programma kan niets downloaden | gebouwd zonder HTTPS-ondersteuning | idem |
| Opslag buiten cloudmappen | `~/GesprekkenLokaal` (niet in iCloud Drive) | `%LOCALAPPDATA%\Gesprekstool\Gesprekken` (niet in OneDrive, zwerft niet mee met het profiel) |
| Waarschuwing bij een cloud- of netwerkmap | ja, de controle keurt dit af | ja |
| Map alleen leesbaar voor de eigen gebruiker | ja | via het gebruikersprofiel |
| Uitgesloten van Time Machine | ja, automatisch | n.v.t. |
| Opname automatisch wissen | 14 dagen na het verslag (instelbaar) | idem |
| Geen browser | het verslag staat in een eigen venster, zodat browserextensies niet kunnen meelezen | idem |

### Wat de school moet regelen

- **Schijfversleuteling** (FileVault of BitLocker) op elke laptop. De tool controleert
  dit op de Mac; op Windows niet.
- **Back-up- en synchronisatiesoftware** mag de opslagmap niet meenemen.
- **Klembord:** *Kopieer verslag* zet de tekst op het klembord. Schakel gedeelde klemborden
  uit (Universeel klembord op de Mac, klembordsynchronisatie op Windows) als dat niet
  gewenst is.
- **Persoonlijke accounts:** elke docent werkt onder een eigen account. Gesprekken staan
  per gebruiker; een beheerder van de laptop kan er technisch wel bij.
- **Het verslag zelf** gaat door de docent naar het leerlingvolgsysteem. Daarvoor gelden
  de bestaande afspraken van de school.

## 5. Instellingen

Instellingen staan in `config.json`. De tool leest ze in deze volgorde; latere winnen:

| Plek | Mac | Windows |
| --- | --- | --- |
| Hele computer (ICT) | `/Library/Application Support/Gesprekstool/config.json` | `C:\ProgramData\Gesprekstool\config.json` |
| Gebruiker | `~/Library/Application Support/Gesprekstool/config.json` | `%LOCALAPPDATA%\Gesprekstool\config.json` |

| Instelling | Standaard | Betekenis |
| --- | --- | --- |
| `audio_bewaren_dagen` | `14` | opname wissen zoveel dagen na het verslag; `0` = nooit automatisch wissen |
| `toestemming_vragen` | `true` | vinkje "Ik heb gemeld dat dit gesprek wordt opgenomen" verplicht |
| `data_map` | leeg | andere opslagmap (alleen een lokale map) |
| `whisper_prompt` | leeg | namen en vaktermen die vaak verkeerd worden verstaan |
| `gpu` | `true` | `false` = alleen de processor gebruiken (bij problemen met de videokaart) |
| `context_tokens` | `0` | hoeveel tekst het taalmodel tegelijk leest; `0` = automatisch |
| `microfoon` | `null` | nummer of naam van een andere microfoon dan de standaardmicrofoon |
| `netwerkblokkade` | `true` | Mac: sandbox zonder netwerk. Laat dit aan staan. |

Voorbeeld voor de hele school:

```json
{ "audio_bewaren_dagen": 7, "whisper_prompt": "mentor, Magister, dyslexie, havo, vwo" }
```

## 6. Templates

Een template is een tekstbestand met de koppen van het verslag. `{datum}` en `{naam}`
worden automatisch ingevuld. Elk `.txt`-bestand verschijnt als keuze in het startscherm.

| Plek | Voor wie |
| --- | --- |
| `<systeemmap>/templates` (zie hoofdstuk 5) | templates van de school, voor alle gebruikers |
| `<gebruikersmap>/templates` | eigen templates van een docent |

Een template met dezelfde naam als een meegeleverd template vervangt dat template.

## 7. Problemen oplossen

| Melding of gedrag | Oplossing |
| --- | --- |
| *Niet klaar voor gebruik: ... model ontbreekt* | modellen staan niet in de map `models` (stap 3 of 4) |
| *Microfoon: geen microfoon gevonden* | sluit een microfoon aan of geef toegang in de privacy-instellingen |
| Balk beweegt niet tijdens de opname | verkeerde microfoon gekozen in het systeem, of geen toegang |
| *Opslagmap ... synchroniseert* | de map staat in een cloud- of netwerkmap; pas `data_map` aan |
| *Het taalmodel kon niet starten* | meestal te weinig werkgeheugen: gebruik het kleine model of sluit andere programma's |
| Verwerken duurt erg lang | gebruik het kleine model; houd de laptop aan de netstroom |
| Programma start niet (Mac, "ontwikkelaar kan niet worden geverifieerd") | installeer via `mac-installeren.sh` of rol uit via MDM |

Per gesprek staat in de map een bestand `verwerking.log` met technische details. Daar
staat geen gespreksinhoud in.

Controle op de opdrachtregel:

```bash
/Applications/Gesprekstool.app/Contents/MacOS/Gesprekstool --controle        # Mac
"C:\Program Files\Gesprekstool\gesprekstool-cli.exe" --controle              # Windows
```

## 8. Advies voor de school: privacy en organisatie

Dit is praktisch advies, geen juridisch oordeel. Leg het voor aan de FG.

1. **Leg vast waarom en wanneer er wordt opgenomen.** Een opname van een gesprek met ouders
   of een leerling is een verwerking van persoonsgegevens, vaak ook gevoelige. Voer een
   DPIA uit of laat de FG beoordelen of die nodig is, en neem de verwerking op in het
   verwerkingsregister.
2. **Informeer vooraf.** Vermeld het gebruik in de privacyverklaring en laat de docent het
   bij elk gesprek melden. Spreek af wat er gebeurt als iemand bezwaar heeft: dan niet
   opnemen.
3. **Bewaar kort.** De opname is alleen nodig om het verslag te maken. Houd de termijn kort
   (standaard 14 dagen) en spreek af dat docenten transcripten en verslagen op de laptop
   verwijderen zodra het verslag in het leerlingvolgsysteem staat.
4. **De docent blijft verantwoordelijk voor het verslag.** Het model kan zich vergissen,
   dingen weglaten of verkeerd toeschrijven. Nalezen is verplicht, niet optioneel.
5. **Begin klein.** Start met een proef van enkele weken met een paar docenten. Meet de
   verwerkingstijd, beoordeel de kwaliteit van de verslagen en pas de templates aan.
6. **Wijs een aanspreekpunt aan** bij ICT voor installatie en vragen, en een bij de
   schoolleiding of FG voor vragen over opnemen en bewaren.

### Licenties

- Gesprekstool, whisper.cpp en llama.cpp: open source.
- Spraakmodel (Whisper): MIT-licentie.
- Taalmodel (Gemma 3 van Google): gratis te gebruiken onder de *Gemma Terms of Use*. Laat
  de school deze voorwaarden lezen en accepteren. Wie een ander model wil gebruiken, zet
  een ander `.gguf`-bestand in de map `models`.

## 9. Wat is getest en wat niet

**Automatisch getest bij elke wijziging**, op echte macOS- en Windows-machines van GitHub,
met het pakket zoals ICT het uitrolt:

| Test | Mac | Windows |
| --- | --- | --- |
| Pakket start en het venster opent | ja | ja |
| Controle van de installatie | ja | ja |
| Netwerkblokkade: verbinding naar buiten wordt geweigerd | ja (sandbox) | firewallregel aanwezig |
| Taalmodel werkt met de netwerkblokkade actief | ja | ja |
| Opname naar transcript naar verslag, met echte spraakherkenning en echt taalmodel | ja | ja |
| Opname van 48 kHz (microfoon die geen 16 kHz levert) | ja | - |
| Opnemen via de microfoon van de testmachine | ja (virtuele microfoon) | - (testmachine heeft er geen) |
| Installatiescripts voor ICT | ja | ja |
| Downloadadressen van de modellen bestaan | ja | ja |

Daarnaast draaien 26 tests met een nagebootste microfoon, spraakherkenning en taalmodel:
het venster van opname tot verslag, pauzeren, annuleren en later afmaken, fouten tijdens
het verwerken, een wegvallende microfoon, lange gesprekken, en het wissen van oude opnames.

De automatische tests gebruiken kleine testmodellen en een Engels fragment. Ze bewijzen
dat de techniek werkt, niet hoe goed de verslagen zijn.

**Nog niet getest: doe dit in de proef op school.**

1. Opnemen met een echte microfoon op een echte laptop, inclusief de toestemmingsvraag
   van macOS.
2. De kwaliteit van Nederlandse transcripten en verslagen met de echte modellen.
3. De verwerkingstijd op de laptops van de school.
4. Het gedrag onder de beveiliging van de school: Gatekeeper, SmartScreen, AppLocker of
   WDAC, en de virusscanner.
5. Gesprekken van een uur of langer.

## 10. Zelf bouwen

De pakketten worden gebouwd door GitHub Actions (`.github/workflows/gesprekstool.yml`) op
echte macOS- en Windows-machines:

1. `bouw/bouw-binaries.sh` bouwt whisper.cpp en llama.cpp uit broncode, met vaste versies.
2. PyInstaller (`bouw/gesprekstool.spec`) maakt van de Python-code een programma.
3. `bouw/maak-pakket.sh` stelt het pakket samen.
4. `bouw/rooktest.sh` draait het echte pakket met kleine testmodellen: controle,
   netwerkblokkade, opname naar verslag, venster openen, en de installatiescripts.
