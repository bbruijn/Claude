# Gesprekstool (volledig offline)

Neemt oudergesprekken en leerlinggesprekken op, transcribeert ze en vat ze samen
volgens een template. Alles draait lokaal op de Mac.

| Stap | Programma | Model |
| --- | --- | --- |
| Opnemen | ffmpeg | – |
| Transcriberen | whisper.cpp | large-v3-turbo |
| Samenvatten | llama.cpp | Gemma 3 (12b bij ≥ 16 GB RAM, anders 4b) |

## Installeren (eenmalig, met internet)

1. Installeer [Homebrew](https://brew.sh) als je dat nog niet hebt.
2. Haal deze map op de Mac en draai:
   ```bash
   cd gesprekstool
   ./install.sh
   ```
3. Wacht tot de modellen binnen zijn (ca. 4–9 GB).
4. Lees de uitvoer van de controle aan het eind: alles moet `OK` zijn.

Daarna is internet niet meer nodig. Je kunt wifi uitzetten.

## Gebruiken

1. Open Terminal en typ `gesprek`.
2. Kies het soort gesprek en vul (optioneel) de naam van de leerling in.
3. Druk op Enter om de opname te stoppen.
4. Wacht op transcript en samenvatting. De map opent vanzelf in Finder.

De eerste keer vraagt macOS om microfoontoegang voor Terminal: kies *Sta toe*.

Per gesprek krijg je een map in `~/GesprekkenLokaal`:

```
2026-11-14_1530_oudergesprek_sam/
  opname.wav        de opname
  transcript.txt    het volledige transcript
  samenvatting.md   het ingevulde template
```

Overige commando's:

| Commando | Doel |
| --- | --- |
| `gesprek verwerk opname.m4a` | bestaand audiobestand verwerken |
| `gesprek samenvat <map> --template leerlinggesprek` | samenvatting opnieuw maken |
| `gesprek controle` | installatie, opslag en netwerkblokkade controleren |
| `gesprek microfoons` | beschikbare microfoons tonen |

## Templates aanpassen

Templates staan in `~/.gesprekstool/templates` als Markdown-bestanden. Pas de koppen
aan of zet er een nieuw `.md`-bestand bij; het verschijnt vanzelf in het keuzemenu.
`{datum}` en `{naam}` worden automatisch ingevuld.

## Instellingen

`~/.gesprekstool/config.json`:

| Instelling | Betekenis |
| --- | --- |
| `data_map` | waar gesprekken worden opgeslagen |
| `microfoon` | `:default` of bijvoorbeeld `:1` (zie `gesprek microfoons`) |
| `verwijder_audio_na_verwerking` | `true` = opname wissen zodra de samenvatting klaar is |
| `whisper_prompt` | namen en vaktermen die vaak verkeerd verstaan worden |
| `sandbox` | netwerkblokkade aan/uit (laat aan) |

## Hoe blijft de data op de laptop

- **Geen netwerk:** ffmpeg, whisper.cpp en llama.cpp draaien in een macOS-sandbox
  die netwerkverkeer op systeemniveau blokkeert. Het taalmodel is alleen bereikbaar
  op `127.0.0.1` (binnen de laptop). Werkt de blokkade niet, dan weigert de tool te starten.
- **Geen cloudmap:** gesprekken staan in `~/GesprekkenLokaal`, buiten iCloud Drive,
  alleen leesbaar voor jouw account.
- **Geen back-up naar buiten:** de map is uitgesloten van Time Machine.
- **Versleuteling:** `gesprek controle` waarschuwt als FileVault uit staat.

Zelf controleren: zet wifi uit en draai `gesprek`. Alles werkt hetzelfde.

Wat de tool niet kan afdwingen: zet de map niet zelf in een cloudmap, en deel
verslagen alleen via de kanalen die je school daarvoor toestaat.

## Beperkingen

- Het transcript labelt geen sprekers.
- Transcript en samenvatting kunnen fouten bevatten: lees het verslag altijd na.
- Informeer ouders en leerlingen vooraf dat het gesprek wordt opgenomen (AVG).

## Verwijderen

```bash
rm -rf ~/.gesprekstool "$(brew --prefix)/bin/gesprek"
```

Gesprekken in `~/GesprekkenLokaal` verwijder je zelf.

## Tests

```bash
python3 -m unittest discover -s gesprekstool/tests -v
```
