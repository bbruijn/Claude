# Schwacke API — Onderzoeksrapport
**Onderdeel van:** Autovista Group (J.D. Power)
**Datum:** 2026-02-20

---

## 1. Wat is Schwacke?

**Schwacke** is een van de meest gezaghebbende automotive data-services in Europa, opgericht door **Hanns W. Schwacke** als uitgever van de eerste gebruikte-autowaardelijst op het Europese continent. De "Schwacke-Liste" is in Duitsland de de facto standaard voor gebruikte-autowaarden — vergelijkbaar met "Glass's Guide" in het VK of "Kelley Blue Book" in de VS.

Schwacke opereert als het **Duitstalig marktgerichte brand** (DACH: Duitsland, Oostenrijk, Zwitserland) binnen Autovista Group, dat in **maart 2024 werd overgenomen door J.D. Power**.

### Autovista Group brands:
| Brand | Markt |
|---|---|
| **Schwacke** | Duitsland / DACH-regio |
| **Eurotax** | Zwitserland, Oostenrijk, overig Europa |
| **Glass's** | VK en Australië |
| **Autovista** | Pan-Europees (Spanje, Frankrijk, etc.) |
| **Rødboka** | Scandinavië |
| **EV Volumes** | Internationaal (EV-marktdata) |

In 2000 fuseerden Eurotax, Schwacke en Glass's tot **EurotaxGlass's** — de Europese marktleider in automotive business intelligence. De huidige API-infrastructuur draagt nog sporen van die fusie (bijv. `webservices.eurotaxglass.com`). Later werd dit omgedoopt tot Autovista Group.

---

## 2. Wat biedt de Schwacke/Autovista API?

De API is commercieel gepositioneerd als de **AutovistaAPI** en bestaat uit vijf functionele modules:

### 2.1 Identificatie (AutovistaIDENT)
Voertuig opzoeken via:
- **VIN** (Vehicle Identification Number)
- **NatCode** (National Vehicle Code — >99% van het Europese wagenpark)
- **Kenteken** (waar wettelijk toegestaan)
- **SchwackeCode** (intern Schwacke-ID)
- **HSN/TSN** (Herstellerschlüsselnummer / Typschlüsselnummer — Duits kentekenstelsel)
- **Merk/model-boom** (browsable hiërarchie)

De teruggegeven NatCode of SchwackeCode is de sleutel naar alle overige modules.

### 2.2 Specificaties (AutovistaSPEC)
- **350+ datavelden per voertuig**, waaronder:
  - Motorgegevens: cilinderinhoud, vermogen, brandstoftype, valves per cilinder, slagen
  - Afmetingen, gewichten, prestatiedata
  - OEM-uitrustingslijsten (standaard én optioneel), inclusief VIN-niveau opties
  - WLTP-emissiedata (ook voor EV en PHEV)
  - EV-specifiek: batterijcapaciteit, actieradius, laadspecificaties
- Dekt **13+ Europese markten**
- Beschikbaar als real-time API én als statische **tab-separated CSV data feeds** (voor bulk database-import)

### 2.3 Waardering (AutovistaVALUATION)
- Actuele en historische marktwaarden per voertuig
- **Kilometerstandcorrectie** (sleutel differentiator t.o.v. statische feeds)
- Waardetype per respons:
  - Trade-in / B2B-waarde
  - Retailwaarde
  - Wegbelasting (landspecifiek; bijv. UK: "RFL")
  - Schadeherstelkostencorrectie
  - Emissiefactorcorrectie
  - BTW-terugvorderingsindicator
- **Maandelijks bijgewerkt**
- Geschiedenis tot **12 jaar (120 maanden)** terug
- Drie waarderingsmodi: Residual Value ("R"), Special Rules ("L"), Proprietary Built-in Rules ("V")
- Dekt **15 Europese markten**

### 2.4 Prognose (AutovistaFORECAST)
- Residual value (RV) forecast voor een toekomstige datum + verwacht kilometrage
- Ondersteunt bulk-uploads (VIN-lijst voor vlootverwerking)
- Tot **16 leeftijd/kilometerstand-scenario's** voor strategische planning
- **Residual Value Index**: vergelijking van waardeontwikkelingen tussen markten

### 2.5 Service, Maintenance & Repair (AutovistaSMR)
- OEM-onderdelen prijzen en arbeidstijden
- Slijtageonderdelen-forecast voor TCO-berekeningen
- **TecDoc-compatibel** (industrie-standaard voor onderdelen-catalogi)
- Reparatiekostenberekening voor schadeclaims (verzekeraars)
- Total Cost of Ownership (TCO)-berekeningen

---

## 3. Technische Architectuur

### 3.1 Legacy API — SOAP/XML (wordt uitgefaseerd)

De historische API is gebaseerd op **SOAP/WSDL over HTTPS**:

**Bekende WSDL-endpoints:**

| Module | WSDL URL |
|---|---|
| Identificatie | `https://webservices.eurotaxglass.com/wsdl/identification.wsdl` |
| Identificatie v2 | `https://webservices.eurotaxglass.com/wsdl/identification-v2.wsdl` |
| Waardering | `https://webservices.eurotaxglass.com/wsdl/valuation.wsdl` |
| Prognose | `https://webservices.eurotaxglass.com/wsdl/forecast.wsdl` |
| Zoeken | `https://webservices2.eurotaxglass.com/wsdl/search.wsdl` |
| VIN Search (internationaal) | `https://vinsearch.eurotaxglass.com/vin-intl/?wsdl` |

**Authenticatie — token-gebaseerd SOAP-flow:**
1. Eerste aanroep bevat username + password in de `ETGHeader` SOAP-header
2. De service retourneert een **security token**
3. Alle volgende aanroepen gebruiken dit token i.p.v. username/password
4. Elke respons bevat een uniek **Order ID** (voor async request-correlatie)

**SOAP-header structuur (versie 2.1.0):**
```xml
<ETGHeader>
  <Version>2.1.0</Version>
  <LoginData>
    <Username>...</Username>
    <Password>...</Password>
  </LoginData>
  <Originator>
    <Signature>...</Signature>
  </Originator>
</ETGHeader>
```

**Requestparameters (identificatie):**
```xml
<Settings>
  <ISOCountry>DE</ISOCountry>       <!-- DE, CH, AT, etc. -->
  <Language>DE</Language>
  <Currency>EUR</Currency>
</Settings>
<VehicleList>
  <VehicleTypeCode>10</VehicleTypeCode>  <!-- 10=PKW, 20=LCV, 60=Motor -->
  <MakeCode>...</MakeCode>
  <ModelCode>...</ModelCode>
</VehicleList>
```

- Dataformaat: **XML**
- Protocol: **SOAP** (Document-literal stijl)
- Transport: **HTTPS** (TLS 1.2 / TLS 1.3 — HTTP gedeactiveerd)
- Ondersteunt zowel synchrone als asynchrone verwerking

### 3.2 Nieuwe REST API (actieve migratie)

Schwacke migreert van SchwackeNet naar een nieuw platform met gestandaardiseerde REST API:

- Protocol: **REST over HTTPS**
- Dataformaat: **JSON**
- Authenticatie: **API key of OAuth 2.0 bearer token** (niet publiek gedocumenteerd)
- **Cloud-hosted**, dynamische IP-adressen (geen IP-whitelisting meer nodig)
- **Verplicht** voor alle DMS-leveranciers — SOAP-API's worden gedeactiveerd
- **Pay-per-use** model

### 3.3 Statische Data Feeds
- Formaat: **Tab-separated CSV**
- Bulk-import in klantdatabases
- Inclusief scripts voor database-aanmaak en laden
- Periodiek geleverd (niet real-time)

---

## 4. Typische Integratievolgorde (Legacy SOAP)

```
1. Identificatie-service aanroepen (VIN / kenteken / HSN/TSN)
        ↓
2. NatCode / SchwackeCode ontvangen
        ↓
3. Waardering-service aanroepen met NatCode + kilometerstand
        ↓
4. (Optioneel) Prognose-service: toekomstige datum + verwacht km
        ↓
5. (Optioneel) SMR-service: onderhouds- en reparatiekosten
```

---

## 5. Authenticatie & Toegang

| Aspect | Legacy (SOAP) | Nieuw (REST) |
|---|---|---|
| Type | Username + Password → security token | API key / OAuth 2.0 (verwacht) |
| IP-restrictie | Historisch: IP-whitelisting | Nee (cloud, dynamisch) |
| Credentials | Via contract verstrekt | Via DMS-partnerportaal |
| Documentatie | Achter commercieel akkoord | Achter commercieel akkoord |
| Test-omgeving | Beschikbaar op aanvraag | Beschikbaar op aanvraag |

**De API is niet publiek beschikbaar** — toegang vereist een B2B-contract met Schwacke/Autovista Group.

---

## 6. Use Cases per Sector

| Sector | Toepassing |
|---|---|
| **Dealers** | Inkoop-/verkoopprijsbepaling, voorraadbeheer |
| **Verzekeraars** | Schadewaardering, reparatiekostenberekening, risico-inschatting op basis van uitrusting (ADAS-features) |
| **Leasemaatschappijen** | RV-forecasting voor leasetariefstelling, contractprijsstelling |
| **Banken / Financiers** | Onderpandwaardering voertuigen |
| **OEM's** | Marktanalyse, prijsstrategie, configuratortools |
| **Vlootbeheer** | TCO-berekeningen, onderhoudsplanning, remarketingtiming |
| **Tweedehands platforms** | Geautomatiseerde taxatie en dynamische pricing |

---

## 7. Dataversheid & Kwaliteit

| Aspect | Detail |
|---|---|
| Data-update cyclus (waardering) | Maandelijks |
| Dagelijkse expertreviews | Ja (feeding in modellen) |
| Historische data | 12 jaar / 120 maanden |
| Voertuigdekking | >99% Europees wagenpark |
| Datavelden per voertuig | 350+ |
| Markten (specs) | 13+ |
| Markten (waardering) | 15 |
| Databron | OEM originele buildata + marktdata |
| EV/PHEV ondersteuning | Ja (WLTP, batterij, range) |

---

## 8. Bekende Integratiepatronen & Community-resources

**Geen officiële SDK of client library** door Autovista/Schwacke gepubliceerd.

| Resource | Type | Link |
|---|---|---|
| PHP SOAP-implementatie (v2.1.0) | Community Gist | [gist.github.com/zyrup](https://gist.github.com/zyrup/3f2b6fd7c78992d62a71ba49d1409bfd) |
| MuleSoft B2B Experience API (Eurotax) | Enterprise integratie | [Fidelidade op Anypoint Exchange](https://eu1.anypoint.mulesoft.com/exchange/portals/fidelidade/e571664f-efac-4062-8354-117d2c9c30d4/motor-eurotax-b2b-xapi/) |
| DMS REST-integraties | Direct, vervangt SOAP | Via Schwacke DMS-portaal |
| Statische CSV feeds | Bulk database-import | Via contract |

---

## 9. Toegang & Documentatie

### Publiek beschikbare bronnen
- Productoverzicht (DE): [schwacke.de/produkt/autovistaapi/](https://schwacke.de/produkt/autovistaapi/)
- API-migratie: [schwacke.de/api-migration/](https://schwacke.de/api-migration/)
- DMS-integratieportaal: [schwacke.de/dms-integration-portal-de/](https://schwacke.de/dms-integration-portal-de/)
- Autovista API (internationaal): [autovista.com/product/autovista-api/](https://autovista.com/product/autovista-api/)
- Legacy WSDL-bestanden: publiek leesbaar op `https://webservices.eurotaxglass.com/wsdl/` (maar API-methoden vereisen credentials)

Volledige technische documentatie (endpoint-schema's, veldwoordenboek, sandbox) is **alleen beschikbaar na commercieel akkoord**.

### Contactpersonen
| Contact | Rol |
|---|---|
| joachim.elsaesser@schwacke.de | DMS-integratie, testen, scoping |
| customer@autovistagroup.com | Algemeen technisch klantcontact |

### Prijsmodel
- **Enterprise B2B contract** (geen self-service of publieke prijslijst)
- **Pay-per-use** (per API-aanroep) of **abonnement** (data feeds)
- Deelmodules mogelijk (bijv. alleen identificatie + waardering)
- Testomgeving beschikbaar op aanvraag

---

## 10. Concurrenten / Alternatieven

| Aanbieder | Markt | Opmerkingen |
|---|---|---|
| **DAT** (Deutsche Automobil Treuhand) | Duitsland | Directe concurrent; VIN- en HSN/TSN-gebaseerd |
| **DEKRA** | Europa | Taxatiediensten |
| **mobile.de API** | Duitsland | Marktplaats-data (advertentieprijzen) |
| **CarQuery / CarAPI** | Internationaal | Publiek, maar minder nauwkeurig en geen RV-data |

---

## 11. Samenvatting & Aanbevelingen

### Sterke punten
- Marktstandaard in Duitsland / DACH voor voertuigwaardering
- Brede data-dekking: 350+ velden, 15 markten, 12 jaar geschiedenis
- Wekelijkse/maandelijkse updates met dagelijkse expertreviews
- TecDoc-compatibel (SMR)
- Sterke positie bij verzekeraars, leasemaatschappijen en dealers
- Actieve modernisering naar REST API
- VIN-niveau precisie (inclusief uitrusting)

### Aandachtspunten
- Geen publieke documentatie of self-service toegang
- Contractueel model vereist onderhandeling
- Lopende migratie SOAP → REST kan integraties tijdelijk verstoren
- Prijsstelling niet transparant
- Geen officiële SDK

### Vervolgstappen voor integratie
1. **Contact opnemen** met Joachim Elsaesser-Grimm (joachim.elsaesser@schwacke.de) voor testomgeving-toegang
2. **NDA / commercieel akkoord** sluiten voor toegang tot volledige API-documentatie
3. **REST API specificaties** opvragen via het DMS-partnerportaal
4. **Testintegratie** bouwen op basis van verstrekte credentials
5. **NatCode / SchwackeCode** als centrale voertuig-identifier in het eigen datamodel opnemen
6. Migratie-tijdlijn opvragen — SOAP-endpoints worden op termijn gedeactiveerd

---

## Bronnen

- [AutovistaAPI - Schwacke.de](https://schwacke.de/produkt/autovistaapi/)
- [Autovista API - autovista.com](https://autovista.com/product/autovista-api/)
- [API Migration - Schwacke.de](https://schwacke.de/api-migration/)
- [DMS Integration Portal - Schwacke.de](https://schwacke.de/dms-integration-portal-de/)
- [AutovistaAPIs HTTP Decommission](https://autovista24.autovistagroup.com/autovistaapis-decommission-of-http/)
- [Autovista Group Acquisition - J.D. Power](https://www.jdpower.com/business/press-releases/autovista-group-acquisition-close)
- [Autovista Group - About Us](https://autovistagroup.com/about-us)
- [SOAP PHP WSDL Gist (Eurotax v2.1.0)](https://gist.github.com/zyrup/3f2b6fd7c78992d62a71ba49d1409bfd)
- [SchwackeNet FAQ](https://schwacke.de/schwackenet-faq/)
- [AutovistaSMR](https://autovista.com/product/service-maintenance-repair-data/)
- [Vehicle Data Feeds & Solutions](https://autovista.com/product/data-solutions/)
- [MuleSoft Eurotax B2B API (Fidelidade)](https://eu1.anypoint.mulesoft.com/exchange/portals/fidelidade/e571664f-efac-4062-8354-117d2c9c30d4/motor-eurotax-b2b-xapi/)
