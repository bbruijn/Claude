# Voorbeeld: een echt verslag van de tool

Dit is de uitkomst van een test met de echte modellen, op een fictief oudergesprek van
anderhalve minuut. Het gesprek is ingesproken met twee computerstemmen (mentor en ouder)
en daarna als opname door de tool verwerkt. Er is niets aan de uitkomst veranderd.

Let op: computerstemmen zijn duidelijker dan een echt gesprek in een lokaal. Een proef
met echte opnamen blijft nodig (zie [BEHEER.md](../BEHEER.md), hoofdstuk 9).

## Wat de test laat zien

- Het transcript is vrijwel foutloos (een schrijffout: "s'avonds").
- Beide verslagen zijn feitelijk juist en volgen het template.
- Het kleine model maakt kleine fouten: "vanaf volgende week" staat bij de verkeerde
  afspraak, en bij *Vervolg* staat "Niet besproken" terwijl er een vervolggesprek is
  afgesproken. Het grote model doet dit goed.
- Wie aanwezig was, is uit de opname niet af te leiden: dat vult de docent zelf in.
- Nalezen blijft dus nodig, vooral bij het kleine model.

## Snelheid

Gemeten op een computer met 4 processorkernen en zonder videokaart.

| Stap | Klein model (4b) | Groot model (12b) |
| --- | --- | --- |
| Uitschrijven van 97 seconden gesprek | 105 s | 105 s (zelfde spraakmodel) |
| Verslag schrijven | 79 s | 253 s |

## Transcript (door de tool gemaakt)

```
Goedemiddag, fijn dat u er bent.
We hebben vandaag het voortgangsgesprek over Sam, naar aanleiding van het eerste rapport.
Zullen we beginnen met hoe het thuis gaat?
Ja, goed. Thuis gaat het eigenlijk wel prima.
Sam gaat met plezier naar school en heeft leuke vrienden.
Maar met het huiswerk gaat het niet zo lekker.
Hij begint er vaak pas om negen uur s'avonds aan en dan is hij moe.
Dat herken ik.
Op school zie ik dat Sam goed meedoet bij Nederlands en geschiedenis.
Daar staat hij een ruime voldoende.
Bij wiskunde gaat het minder.
Hij staat nu een 5,1.
Hij vraagt in de les weinig hulp als hij iets niet snapt.
Ja, wiskunde vindt hij lastig.
Hij zegt thuis dat hij de uitleg te snel vindt gaan.
Maar hij durft dat niet te zeggen in de klas.
Goed dat u dat zegt.
Wat wel heel goed gaat, Sam is behulpzaam en werkt prettig samen met klasgenoten.
Docenten zijn daar positief over.
Dat is fijn om te horen.
Wat kunnen we doen aan het plannen en aan wiskunde?
Ik stel voor dat Sam een weekplanner gaat gebruiken.
Die bespreek ik elke maandag met hem in het mentoruur.
Vanaf volgende week.
En voor wiskunde kan hij naar de steunles op dinsdag het zevende uur.
Ik meld hem daarvoor aan.
Prima, dan spreken wij thuis af dat we op zondagavond samen met Sam naar de planning voor de week kijken.
En zijn telefoon gaat tijdens het huiswerk naar beneden.
Heel goed.
Dan plannen we over zes weken een vervolggesprek om te kijken of het werkt.
Ik stuur u daarvoor een uitnodiging.
Dank u wel.
Tot over zes weken.
```

## Verslag met het grote model (Gemma 3, 12b)

```
VERSLAG OUDERGESPREK

Datum: 14-11-2026 10:59
Leerling: Sam de Vries
Aanwezig: Niet besproken

AANLEIDING EN DOEL VAN HET GESPREK
Voortgangsgesprek naar aanleiding van het eerste rapport.

HOE GAAT HET MET DE LEERLING (THUIS EN OP SCHOOL)
Thuis gaat het wel prima. Sam gaat met plezier naar school en heeft leuke vrienden. Met het huiswerk gaat het niet zo lekker. Hij begint er vaak pas om negen uur 's avonds aan en dan is hij moe.

LEERRESULTATEN EN WERKHOUDING
Sam doet goed mee bij Nederlands en geschiedenis, daar staat hij een ruime voldoende. Bij wiskunde gaat het minder, hij staat een 5,1. Hij vraagt in de les weinig hulp als hij iets niet snapt. Hij vindt wiskunde lastig en vindt de uitleg te snel gaan, maar durft dat niet te zeggen in de klas.

WAT GAAT GOED
Sam is behulpzaam en werkt prettig samen met klasgenoten.

ZORGEN EN AANDACHTSPUNTEN
Het huiswerk wordt te laat begonnen, waardoor Sam moe is. Bij wiskunde gaat het minder en hij durft geen hulp te vragen.

AFSPRAKEN (WAT, WIE, WANNEER)
- Sam gebruikt een weekplanner, die elke maandag in het mentoruur wordt besproken (vanaf volgende week).
- Sam gaat naar de steunles wiskunde op dinsdag het zevende uur.
- Thuis wordt op zondagavond samen met Sam de planning voor de week bekeken.
- De telefoon gaat tijdens het huiswerk naar beneden.
- Er volgt een vervolggesprek over zes weken.

VERVOLG
Een uitnodiging voor het vervolggesprek wordt verstuurd.
```

## Verslag met het kleine model (Gemma 3, 4b)

```
VERSLAG OUDERGESPREK

Datum: 14-11-2026 10:59
Leerling: Sam de Vries
Aanwezig: Ouder

AANLEIDING EN DOEL VAN HET GESPREK

Het gesprek betreft het voortgangsgesprek over Sam de Vries, naar aanleiding van het eerste rapport.

HOE GAAT HET MET DE LEERLING (THUIS EN OP SCHOOL)

Thuis gaat het goed. Sam gaat met plezier naar school en heeft leuke vrienden. Hij begint vaak pas om negen uur s'avonds met zijn huiswerk en is dan moe.

LEERRESULTATEN EN WERKHOUDING

Bij Nederlands en geschiedenis staat Sam een ruime voldoende. Bij wiskunde staat hij nu een 5,1. Hij vraagt in de les weinig hulp als hij iets niet snapt. Hij zegt thuis dat hij de uitleg te snel vindt gaan, maar durft dat niet in de klas te zeggen.

WAT GAAT GOED

Sam is behulpzaam en werkt prettig samen met klasgenoten. Docenten zijn daar positief over.

ZORGEN EN AANDACHTSPUNTEN

Sam heeft moeite met het plannen en uitvoeren van zijn huiswerk. Hij heeft moeite met wiskunde.

AFSPRAKEN (WAT, WIE, WANNEER)

- Sam gaat met een weekplanner werken, besproken met de mentor in het mentoruur elke maandag.
- Vanaf volgende week wordt Sam aangemeld voor een steunles op dinsdag het zevende uur.
- Thuis wordt elke zondagavond samen met Sam gekeken naar de planning voor de week.
- Sam's telefoon gaat tijdens het huiswerk naar beneden.
- Er is een vervolggesprek over zes weken, met een uitnodiging die de mentor zal sturen.

VERVOLG

Niet besproken
```
