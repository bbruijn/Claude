# Interval Timer — iPhone-app

Native iOS-versie van de interval timer. Dezelfde training als de webapp in
`../interval-timer`, maar met audio die een webapp niet kan leveren:

- **Piepjes door je muziek heen.** De audiosessie draait op `.playback` met
  `.mixWithOthers`, dus Spotify blijft spelen en de tonen komen erdoorheen.
  Bewust géén `.duckOthers`: dat zou je muziek de hele training zachter zetten
  in plaats van alleen tijdens een piepje.
- **Geluid met het scherm op slot en in een andere app.** De achtergrondmodus
  `audio` houdt de app draaiend zolang er audio speelt; daarom loopt er tijdens
  een training een stille buffer mee.
- **Klinkt ook in stille stand,** omdat `.playback` niet naar het belschuifje
  luistert.

## Bouwen en op je telefoon zetten

Je hebt een Mac met Xcode nodig, en een kabel of hetzelfde wifi-netwerk.

1. Open `IntervalTimer.xcodeproj` in Xcode (16 of nieuwer).
2. Klik links op het blauwe projecticoon → target **IntervalTimer** → tab
   **Signing & Capabilities**.
3. Zet **Team** op je eigen Apple ID (`Add an Account…` als er nog geen staat;
   een gratis Apple ID volstaat).
4. Verander **Bundle Identifier** in iets unieks, bijvoorbeeld
   `nl.jouwnaam.intervaltimer` — `com.example.intervaltimer` wordt geweigerd.
5. Sluit je iPhone aan en kies hem bovenin als doel.
6. Druk op ▶︎ (Cmd-R).
7. Eerste keer op de telefoon: **Instellingen → Algemeen → VPN en
   apparaatbeheer** → vertrouw je ontwikkelaarsprofiel.

Met een gratis Apple ID verloopt de app na 7 dagen; opnieuw bouwen vernieuwt
hem. Met een betaald Developer Program-account (99 dollar per jaar) is dat een
jaar.

Opent het project niet in een oudere Xcode? Genereer het opnieuw:
`brew install xcodegen && xcodegen generate`.

## Hoe het in elkaar zit

| Bestand | Rol |
| --- | --- |
| `Workout.swift` | De vijf instellingen en het programma dat eruit volgt |
| `WorkoutEngine.swift` | De klok: welk segment loopt, wanneer welk piepje |
| `AudioCoach.swift` | Audiosessie, gesynthetiseerde tonen, stille keep-alive |
| `ContentView.swift` | Het scherm: hero met klok, gekleurde instellingsrijen |
| `EditFieldSheet.swift` | Bewerken met wielen en presets |
| `SavedWorkoutsSheet.swift` | "Laad Vorige Training" |
| `Theme.swift` | Kleuren per fase en per rij |

### Rekenwijze

Per ronde krijgt elke oefening een werk- en een rustinterval; tussen rondes
komt eventueel de ronde-reset. De laatste rust vervalt, want de training
eindigt na het laatste werkinterval.

Voorbeeld: 01:00 werk, 01:30 rust, 1 oefening, 8 rondes
→ `8 × (60 + 90) − 90 = 1110 s = 18:30`.

De klok rekent met absolute tijdstippen (`Date`), niet met opgetelde tikken,
dus de timer loopt niet weg als iOS de app even minder aandacht geeft.
