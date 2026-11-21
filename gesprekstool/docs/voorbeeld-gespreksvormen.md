# Voorbeeld: gespreksvormen met aanwijzingen

Uitkomst van een test van versie 1.2.0 met de echte taalmodellen (Gemma 3, 12b en 4b), op
een computer met 4 processorkernen en zonder videokaart. Er is niets aan de verslagen
veranderd.

## Teamvergadering

Het transcript hieronder is een **fictieve vergadering**, voor deze test geschreven zoals de
spraakherkenning het zou opleveren: zonder sprekers. Er zit bewust in: twee besluiten, een
voorstel waarover geen besluit valt, een actiepunt met en een zonder naam, en een
persoonlijke mededeling over een collega die niet in het verslag hoort.

```
Goedemiddag allemaal, laten we beginnen. We hebben vandaag drie punten: de rapportvergadering, de excursie naar Den Haag en het nieuwe huiswerkbeleid.
Eerst de rapportvergadering. De cijfers moeten uiterlijk vrijdag 12 december in het systeem staan.
Dat is krap, kan het niet de maandag erna?
Nee, de vergadering is op dinsdag 16 december, dus vrijdag blijft de deadline.
Oké, dan houden we vrijdag 12 december aan. Dat is dan besloten.
Dan de excursie naar Den Haag voor de derde klassen. Het Tweede Kamergebouw kan op 20 maart.
Ik vind 20 maart prima, maar we hebben nog geen begeleiders.
We hebben minstens zes begeleiders nodig. Wie meldt zich aan?
Ik wil wel, en Sanne zei vorige week ook dat ze mee wil.
Fijn. Marco, kun jij de bus regelen? Graag voor de kerstvakantie.
Ja, dat doe ik.
Dan zetten we de excursie vast op 20 maart.
Het derde punt is het huiswerkbeleid. Het voorstel is om in de onderbouw geen huiswerk meer op te geven op vrijdag.
Ik zie daar voordelen in, maar ouders gaan daar vragen over stellen.
Klopt, en we weten nog niet hoe de bovenbouw erover denkt.
Zullen we het eerst met de bovenbouwcollega's bespreken voordat we iets besluiten?
Ja, laten we dat doen. We nemen het mee naar de vergadering in januari.
Iemand moet de ouderbrief over de excursie schrijven.
Dat pak ik op, maar ik weet nog niet wanneer ik eraan toekom.
Nog één ding: Pieter is deze week ziek thuis, hij heeft een operatie gehad, dus zijn lessen worden opgevangen.
Goed, dan sluiten we af. Dank jullie wel.
```

### Groot model (12b), 182 seconden

```
VERSLAG TEAMVERGADERING

Datum: 21-11-2026 15:00
Team of onderwerp: Onderbouw
Aanwezig: Niet besproken

BESPROKEN PUNTEN
- Rapportvergadering
- Excursie naar Den Haag voor de derde klassen
- Nieuw huiswerkbeleid

BESLUITEN
- De cijfers voor de rapportvergadering moeten uiterlijk vrijdag 12 december in het systeem staan.
- De excursie naar Den Haag staat vast op 20 maart.

ACTIEPUNTEN (WAT, WIE, WANNEER)
- Bus regelen voor de excursie naar Den Haag. Marco, voor de kerstvakantie.
- Ouderbrief over de excursie schrijven. Wie, niet bekend, wanneer niet bekend.

OPEN PUNTEN VOOR EEN VOLGENDE VERGADERING
- Bespreken van het nieuwe huiswerkbeleid met de bovenbouwcollega's.
```

Beoordeling: goed. Beide besluiten kloppen, het huiswerkbeleid staat terecht bij de open
punten, het actiepunt zonder naam staat er als "niet bekend", en de mededeling over de
collega is weggelaten. Niet opgenomen: dat er nog begeleiders voor de excursie nodig zijn.

### Klein model (4b), 52 seconden

```
VERSLAG TEAMVERGADERING

Datum: 21-11-2026 15:00
Team of onderwerp: Onderbouw
Aanwezig:

BESPROKEN PUNTEN

- Rapportvergadering: Cijfers moeten uiterlijk vrijdag 12 december in het systeem staan.
- Excursie naar Den Haag: Bezoek Tweede Kamergebouw op 20 maart.
- Huiswerkbeleid: Geen huiswerk meer op vrijdag in de onderbouw.

ACTIEPUNTEN (WAT, WIE, WANNEER)

- Marco regelt de bus voor de excursie naar Den Haag, voor de kerstvakantie.
- Iemand schrijft de ouderbrief over de excursie naar Den Haag.

OPEN PUNTEN VOOR EEN VOLGENDE VERGADERING

- Bespreken van het huiswerkbeleid met de bovenbouwcollega’s.
- Hoe de bovenbouw denkt over het huiswerkbeleid.
```

Beoordeling: niet betrouwbaar genoeg. De kop BESLUITEN ontbreekt, en het voorstel over het
huiswerkbeleid staat er als feit. Gebruik voor teamvergaderingen daarom het grote model.

## Oudergesprek: zonder en met aanwijzingen

Hetzelfde ingesproken oudergesprek als in [voorbeeld-echte-test.md](voorbeeld-echte-test.md),
samengevat met het template zonder kop en met de nieuwe aanwijzingen.

### Groot model (12b), met aanwijzingen, 269 seconden

```
VERSLAG OUDERGESPREK

Datum: 21-11-2026 15:00
Leerling: Sam de Vries
Aanwezig: Niet besproken

AANLEIDING EN DOEL VAN HET GESPREK
Voortgangsgesprek naar aanleiding van het eerste rapport.

HOE GAAT HET MET DE LEERLING (THUIS EN OP SCHOOL)
Thuis gaat het wel prima. Sam gaat met plezier naar school en heeft leuke vrienden. Met het huiswerk gaat het niet zo lekker, hij begint er vaak pas om negen uur 's avonds aan en dan is hij moe.

LEERRESULTATEN EN WERKHOUDING
Sam doet goed mee bij Nederlands en geschiedenis, hij staat een ruime voldoende. Bij wiskunde gaat het minder, hij staat een 5,1. Hij vraagt in de les weinig hulp als hij iets niet snapt. Hij vindt wiskunde lastig en vindt de uitleg te snel gaan, maar durft dat niet te zeggen in de klas. Sam is behulpzaam en werkt prettig samen met klasgenoten.

WAT GAAT GOED
Sam is behulpzaam en werkt prettig samen met klasgenoten.

ZORGEN EN AANDACHTSPUNTEN
Het huiswerk wordt pas laat gedaan. Bij wiskunde gaat het minder, hij vindt de uitleg te snel gaan en vraagt weinig hulp.

AFSPRAKEN (WAT, WIE, WANNEER)
- Sam gebruikt een weekplanner, die elke maandag in het mentoruur wordt besproken, vanaf volgende week.
- Sam gaat naar de steunles wiskunde op dinsdag het zevende uur.
- Thuis wordt op zondagavond samen met Sam de planning voor de week bekeken.
- De telefoon gaat tijdens het huiswerk naar beneden.
- Er volgt een vervolggesprek over zes weken.

VERVOLG
Er wordt een uitnodiging voor een vervolggesprek over zes weken verstuurd.
```

Beoordeling: goed en vergelijkbaar met het verslag zonder aanwijzingen in
voorbeeld-echte-test.md.

### Klein model (4b), zonder aanwijzingen

```
VERSLAG OUDERGESPREK

Datum: 21-11-2026 15:00
Leerling: Sam de Vries
Aanwezig: Ouder

AANLEIDING EN DOEL VAN HET GESPREK

Het gesprek betreft het voortgangsgesprek over Sam de Vries, naar aanleiding van het eerste rapport.

HOE GAAT HET MET DE LEERLING (THUIS EN OP SCHOOL)

Thuis gaat het goed. Sam gaat met plezier naar school en heeft leuke vrienden. Hij begint vaak pas om negen uur s'avonds met zijn huiswerk en is dan moe.

LEERRESULTATEN EN WERKHOUDING

Bij Nederlands en geschiedenis staat Sam een ruime voldoende. Bij wiskunde staat hij nu een 5,1. Hij vraagt in de les weinig hulp als hij iets niet snapt.

WAT GAAT GOED

Sam is behulpzaam en werkt prettig samen met klasgenoten. Docenten zijn daar positief over.

ZORGEN EN AANDACHTSPUNTEN

Sam heeft moeite met het plannen van zijn huiswerk en wiskunde vindt hij lastig. Hij zegt thuis dat hij de uitleg te snel vindt gaan, maar durft dit niet in de klas te zeggen.

AFSPRAKEN (WAT, WIE, WANNEER)

- Sam gaat vanaf volgende week een weekplanner gebruiken, besproken met de mentor in het mentoruur.
- Sam meldt zich aan voor de steunles op dinsdag het zevende uur.
- Thuis wordt elke zondagavond samen met Sam gekeken naar de planning voor de week.
- Tijdens het huiswerk wordt Sams telefoon naar beneden gezet.
- Er is een vervolggesprek over zes weken, met een uitnodiging die naar de ouder gestuurd zal worden.

VERVOLG

Niet besproken
```

### Klein model (4b), met aanwijzingen

```
VERSLAG OUDERGESPREK

Datum: 21-11-2026 15:00
Leerling: Sam de Vries
Aanwezig: Ouder

AANLEIDING EN DOEL VAN HET GESPREK

Het gesprek heeft plaatsgevonden ter beoordeling van het eerste rapport van Sam de Vries.

HOE GAAT HET MET DE LEERLING (THUIS EN OP SCHOOL)

Thuis gaat het goed. Sam gaat met plezier naar school en heeft leuke vrienden. Hij begint vaak pas om negen uur s'avonds met zijn huiswerk en is dan moe.
Op school zie ik dat Sam goed meedoet bij Nederlands en geschiedenis. Hij staat daar een ruime voldoende. Bij wiskunde gaat het minder, hij staat nu een 5,1.

LEERRESULTATEN EN WERKHOUDING

Sam staat een 5,1 in wiskunde. Hij vraagt in de les weinig hulp als hij iets niet snapt. Hij zegt thuis dat hij de uitleg te snel vindt gaan, maar hij durft dat niet te zeggen in de klas.
Sam is behulpzaam en werkt prettig samen met klasgenoten. Docenten zijn daar positief over.

WAT GAAT GOED

Sam is behulpzaam en werkt prettig samen met klasgenoten.
Sam doet goed mee bij Nederlands en geschiedenis.

ZORGEN EN AANDACHTSPUNTEN

Sam heeft moeite met het plannen van zijn huiswerk. Hij begint er vaak pas om negen uur s'avonds aan en is dan moe.
Sam heeft moeite met wiskunde.

AFSPRAKEN (WAT, WIE, WANNEER)

Sam gaat vanaf volgende week een weekplanner gebruiken. Deze wordt elke maandag met hem besproken in het mentoruur.
Sam meld zich aan voor de steunles op dinsdag het zevende uur.
Thuis wordt er elke zondagavond samen met Sam gekeken naar de planning voor de week.
De ouder en Sam stemmen overeen om over zes weken een vervolggesprek te houden.

VERVOLG

Niet besproken
```

Beoordeling: beide verslagen van het kleine model bevatten fouten, elk andere. Zonder
aanwijzingen staat er dat Sam zichzelf aanmeldt voor de steunles (de mentor doet dat) en
mist het vervolggesprek bij *Vervolg*. Met aanwijzingen valt de afspraak over de telefoon
weg, staat er informatie dubbel en is een zin van de mentor letterlijk overgenomen ("Op
school zie ik dat..."). Een enkele vergelijking is te weinig om te zeggen welke versie beter
is; beoordeel dit in de proef met meer gesprekken.

## Conclusie

- Met het grote model doen de aanwijzingen wat ze moeten doen: het verslag volgt de
  structuur en let op wat bij de gespreksvorm belangrijk is.
- Het kleine model volgt template en aanwijzingen minder goed. Voor teamvergaderingen is het
  niet geschikt; voor ouder- en leerlinggesprekken is nalezen extra belangrijk.
