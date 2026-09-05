# Interval Timer

Een interval-trainingstimer voor de iPhone, gebouwd als PWA (webapp). Voeg hem
toe aan je beginscherm en hij draait volledig schermvullend en offline, zonder
App Store of Xcode.

## Functies

| Rij | Betekenis |
| --- | --- |
| **Laad Vorige Training** | Kies een eerder opgeslagen training terug |
| **Werk** | Duur van een werkinterval |
| **Uitrusten** | Duur van de rust na elk werkinterval |
| **Oefeningen** | Aantal oefeningen per ronde |
| **Rondes** | Aantal rondes |
| **Ronde resetten** | Extra pauze tussen twee rondes |

Verder:

- Grote klok met fasekleur: oranje (klaar om te starten), groen (werk),
  rood (rust), geel (ronde resetten).
- Ronde- en oefeningteller, voortgangsbalk en resterende totaaltijd.
- Pieptonen bij aftellen (3-2-1), bij elke fasewissel en aan het einde,
  plus trilling waar het apparaat dat ondersteunt. Geluid is uit te zetten.
- Scherm blijft aan tijdens de training (Screen Wake Lock).
- Start/pauze/herstel, instellingen worden lokaal bewaard.
- Werkt offline via een service worker.

### Rekenwijze

Per ronde krijgt elke oefening een werk- en een rustinterval; tussen rondes
komt eventueel de ronde-reset. De allerlaatste rust vervalt, want de training
eindigt na het laatste werkinterval.

Voorbeeld: 01:00 werk, 01:30 rust, 1 oefening, 8 rondes
→ `8 × (60 + 90) − 90 = 1110 s = 18:30`.

## Gebruiken

Lokaal testen:

```bash
cd interval-timer
python3 -m http.server 8000
# open http://localhost:8000 op je computer
```

Op de iPhone:

1. Open **https://bbruijn.github.io/Claude/** in Safari. Die pagina wordt door
   `.github/workflows/pages.yml` automatisch bijgewerkt bij elke wijziging in
   `interval-timer/` op `main`. (Https is nodig: service worker en wake lock
   werken alleen via https of localhost.)
2. Wacht bij de eerste keer tot de workflow groen is (tabblad Actions).
3. Deelknop → **Zet op beginscherm**.
4. Start hem vanaf het beginscherm: geen browserbalken, eigen icoon.

## Bestanden

- `index.html` — opbouw van het scherm
- `styles.css` — donker thema, gekleurde rijen, landschapsindeling
- `app.js` — programma-opbouw, klok, geluid, opslag
- `sw.js`, `manifest.webmanifest`, `icons/` — installeerbaar en offline
