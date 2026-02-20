# Schwacke API — Onderzoeksrapport
**Onderdeel van:** Autovista Group (J.D. Power)
**Datum:** 2026-02-20

---

## 1. Wat is Schwacke?

**Schwacke** is een van de leidende automotive data-brands in Duitsland, opgericht in 1957 als uitgever van de bekende "Schwacke-Liste" — de standaardlijst voor gebruikte-autowaarden in Duitsland. Schwacke maakt deel uit van de **Autovista Group**, die in **maart 2024 werd overgenomen door J.D. Power**.

### Autovista Group brands:
| Brand | Markt |
|---|---|
| **Schwacke** | Duitsland |
| **Eurotax** | Zwitserland, Oostenrijk, overig Europa |
| **Glass's** | VK |
| **Autovista** | Overig Europa (Spanje, Frankrijk, etc.) |
| **Rødboka** | Noorwegen |
| **EV Volumes** | Internationaal (EV-marktdata) |

In 2000 fuseerden Eurotax, Schwacke en Glass's tot **EurotaxGlass's** — de Europese marktleider in automotive business intelligence. De huidige API-infrastructuur draagt nog sporen van die fusie (bijv. `webservices.eurotaxglass.com`).

---

## 2. Wat biedt de Schwacke/Autovista API?

De API biedt data over de gehele levenscyclus van een voertuig, gegroepeerd in de volgende categorieën:

### 2.1 Voertuigidentificatie
- Zoeken via **SchwackeCode** (unieke interne code)
- Zoeken via **VIN** (Vehicle Identification Number)
- Zoeken via **HSN/TSN** (Herstellerschlüsselnummer / Typschlüsselnummer — Duits kentekensysteem)
- Zoeken via **merk/model-boom** (browsable tree)
- Zoeken via **NatCode** (internationale Autovista-code, identificeert >97% Europese voertuigen via kenteken)

De centrale **SchwackeCode** en **NatCode** zijn de sleutels die toegang geven tot het volledige data-ecosysteem.

### 2.2 Specificaties
- Motorgegevens (cilinderinhoud, vermogen, brandstoftype, emissienorm)
- Afmetingen en gewichten
- OEM-uitrustingsopties (standaard + optioneel)
- WLTP-emissiedata (inclusief elektrische en hybride voertuigen)
- Historische lijst- en uitrustingsprijzen

### 2.3 Waardering & Prognose
- **Schwacke-Lijst**: marktwaarden voor gebruikte voertuigen (wekelijks bijgewerkt)
- **Residual Value (RV) forecasting**: waardeontwikkeling tot 120 maanden vooruit
- **16 leeftijd/kilometerstand-scenario's** voor strategische planning
- **Residual Value Index**: vergelijking van waardeontwikkelingen tussen markten

### 2.4 Service, Maintenance & Repair (SMR)
- OEM-onderdelen prijzen
- Arbeidstijden per reparatie
- Slijtageonderdelen per voertuig
- **TecDoc-compatibel** (industrie-standaard voor onderdelen-catalogi)
- Ondersteuning voor reparatiekostenberekeningen (schadecalculatie voor verzekeraars)

### 2.5 Total Cost of Ownership (TCO)
- Berekening van de totale eigendomskosten over de levensduur
- Combinatie van afschrijving, onderhoud, brandstof/energie, verzekering

---

## 3. Technische Architectuur

### 3.1 Legacy API (SOAP — wordt uitgefaseerd)
De historische API is gebaseerd op **SOAP/WSDL**:

```
WSDL Endpoint: https://webservices.eurotaxglass.com/wsdl/identification-v2.wsdl
```

- Protocol: **SOAP over HTTPS** (TLS 1.2 / 1.3 vereist — HTTP is gedeactiveerd)
- Dataformaat: **XML**
- Authenticatie: **Header-based credentials** (ETGHeader met username/password + signature)
- Versie: 2.1.0

**Voorbeeld SOAP-header structuur:**
```xml
<ETGHeader>
  <Originator>
    <Signature>[credential]</Signature>
    <LoginData>
      <Username>[username]</Username>
      <Password>[password]</Password>
    </LoginData>
    <Version>2.1.0</Version>
  </Originator>
</ETGHeader>
```

**Voorbeeld requestparameters (GetListVehicleType):**
```xml
<Settings>
  <ISOCountry>DE</ISOCountry>  <!-- of CH, AT, etc. -->
  <Language>DE</Language>
  <Currency>EUR</Currency>
</Settings>
<VehicleList>
  <VehicleTypeCode>10</VehicleTypeCode>  <!-- 10=PKW, 20=LCV, 60=Motor -->
</VehicleList>
```

### 3.2 Nieuwe REST API (actief in migratie)
Schwacke migreert van SchwackeNet naar het **nieuwe Schwacke-platform** met een nieuwe, gestandaardiseerde REST API:

- Protocol: **REST over HTTPS**
- Dataformaat: **JSON** (vermoedelijk)
- Authenticatie: Details beschikbaar via het DMS-integratieportaal (niet publiek)
- **Verplicht** voor alle DMS-leveranciers: de SOAP-API's worden gedeactiveerd
- Cloud-based, **pay-per-use** model

De nieuwe API is de enige toegangsweg tot het nieuwe Schwacke-platform. Na de migratie krijgen bestaande SchwackeNet-klanten pas weer volledige toegang wanneer hun DMS de nieuwe REST-interface heeft geïntegreerd.

---

## 4. Authenticatie & Toegang

| Aspect | Legacy (SOAP) | Nieuw (REST) |
|---|---|---|
| Type | Username + Password in XML-header | Niet publiek gedocumenteerd |
| Credentials | Verstrekt door Autovista/Schwacke | Via DMS-partnerportaal |
| Toegang | Contractueel | Contractueel |
| Test-omgeving | Beschikbaar op aanvraag | Beschikbaar op aanvraag |

**De API is niet publiek beschikbaar** — toegang vereist een contract met Schwacke/Autovista Group.

---

## 5. Use Cases

| Sector | Toepassing |
|---|---|
| **Dealers** | Voertuiginkoop-/verkoopprijsbepaling, voorraadbeheer |
| **Verzekeraars** | Schadewaardering, reparatiekostenberekening, risico-inschatting op basis van uitrusting |
| **Leasemaatschappijen** | Residual value forecasting, contractprijsstelling |
| **Banken/Financiers** | Onderpandwaardering van voertuigen |
| **OEM's** | Marktanalyse, prijsstrategie |
| **Tweedehands platforms** | Geautomatiseerde taxatie en pricing |

---

## 6. Dataversheid & Kwaliteit

- Data wordt **wekelijks bijgewerkt**
- Bevat **originele OEM-buildata** (direct van fabrikant)
- Dekt vrijwel **alle Europese voertuigen**
- Historische data beschikbaar (lijst- en uitrustingsprijzen door de jaren)
- Speciaal aandacht voor **EV en PHEV** voertuigen (WLTP, batterij, range)

---

## 7. Toegang & Integratie

### Documentatie
- Officieel productoverzicht: [schwacke.de/produkt/autovistaapi/](https://schwacke.de/produkt/autovistaapi/)
- API-migratie informatie: [schwacke.de/api-migration/](https://schwacke.de/api-migration/)
- DMS-integratieportaal: [schwacke.de/dms-integration-portal-de/](https://schwacke.de/dms-integration-portal-de/)
- Autovista API (internationaal): [autovista.com/product/autovista-api/](https://autovista.com/product/autovista-api/)

Publieke API-documentatie (Swagger/OpenAPI spec) is **niet vrij beschikbaar** — technische documentatie wordt gedeeld via het partnerportaal na contractsluiting.

### Contactpersonen
- **DMS-integratie / testen:** Joachim Elsaesser-Grimm — joachim.elsaesser@schwacke.de
- **Algemeen klantcontact:** customer@autovistagroup.com

### Prijsmodel
- **Enterprise contract** (geen self-service / geen publieke prijslijst)
- **Pay-per-use** model voor cloud API-calls
- Testomgeving beschikbaar op aanvraag

---

## 8. Concurrenten / Alternatieven

| Aanbieder | Markt | Opmerkingen |
|---|---|---|
| **DAT** (Deutsche Automobil Treuhand) | Duitsland | Directe concurrent; ook VIN-gebaseerd |
| **DEKRA Fahrzeugbewertung** | Europa | Taxatiediensten |
| **mobile.de API** | Duitsland | Marktplaats-data (advertentieprijzen) |
| **CarQuery / CarAPI** | Internationaal | Publiek, maar minder nauwkeurig |

---

## 9. Samenvatting & Aanbevelingen

### Sterke punten
- Marktstandaard in Duitsland voor voertuigwaardering
- Brede data-dekking (specs, waarden, SMR, TCO)
- Wekelijkse updates
- TecDoc-compatibel
- Sterke positie bij verzekeraars en leasemaatschappijen
- Actieve migratie naar moderne REST-architectuur

### Aandachtspunten
- Geen publieke documentatie of self-service toegang
- Contractueel toegangsmodel vereist onderhandeling
- Lopende migratie van SOAP → REST kan integraties verstoren
- Prijsstelling niet transparant

### Vervolgstappen voor integratie
1. **Contact opnemen** met Joachim Elsaesser-Grimm voor testomgeving-toegang
2. **NDA/contract** afsluiten voor toegang tot API-documentatie
3. **REST API specificaties** opvragen via het DMS-partnerportaal
4. **Testintegratie** bouwen op basis van verstrekte credentials
5. **SchwackeCode / NatCode** als centrale identificator gebruiken in data-model

---

*Bronnen:*
- [AutovistaAPI - Schwacke.de](https://schwacke.de/produkt/autovistaapi/)
- [Autovista API - autovista.com](https://autovista.com/product/autovista-api/)
- [API Migration - Schwacke.de](https://schwacke.de/api-migration/)
- [DMS Integration Portal - Schwacke.de](https://schwacke.de/dms-integration-portal-de/)
- [AutovistaAPIs HTTP Decommission](https://autovista24.autovistagroup.com/autovistaapis-decommission-of-http/)
- [Autovista Group Acquisition - J.D. Power](https://www.jdpower.com/business/press-releases/autovista-group-acquisition-close)
- [SOAP PHP WSDL Gist (Eurotax v2.1.0)](https://gist.github.com/zyrup/3f2b6fd7c78992d62a71ba49d1409bfd)
- [SchwackeNet FAQ](https://schwacke.de/schwackenet-faq/)
