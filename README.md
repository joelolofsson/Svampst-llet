# Svampstället

**Svampstället** är en Android-applikation och ett geodatasystem utvecklat för svampplockare i Sverige. Appen kombinerar maskininlärning, ekologiska habitatmodeller, skogliga volymdata och hydrologiska markfuktighetskartor för att identifiera exakta hotspots för svamp – direkt i telefonen, med fullt stöd för offline-användning ute i vildmarken.

Projektet fokuserar initialt på **Trattkantarell (*Craterellus tubaeformis*)**, med **Gul kantarell (*Cantharellus cibarius*)** som kommande funktion.

---

## Innehållsförteckning
1. [Översikt & Huvudfunktioner](#översikt--huvudfunktioner)
2. [Geodata & Källor](#geodata--källor)
3. [Geoprocessering & Pipeline (GDAL)](#geoprocessering--pipeline-gdal)
4. [Ekologisk Algoritm & Habitatmodellering](#ekologisk-algoritm--habitatmodellering)
5. [Applikationsarkitektur & Teknik](#applikationsarkitektur--teknik)
6. [Bygg- och Installationsguide](#bygg--och-installationsguide)
7. [Versionshantering & Git](#versionshantering--git)

---

## Översikt & Huvudfunktioner

- **Interaktiv Karta med Skiktade Kartlager:** Växla sömlöst mellan högupplösta satellitbilder (ESRI World Imagery), topografisk terrängkarta (Liberty) och ren stad/vägkarta (Positron).
- **Ekologiska Hotspot-Lager:** Renderar predicerade växtplatser med färgintensitet baserad på habitatets kvalitet (40 % till 100 % sannolikhet).
- **Skogstyp & Kalhyggen som Karta:** Tydlig färgkodning över skogssammansättning:
  - Mörkgrön: Grandominerad skog (> 45 % gran)
  - Orange/Bärnsten: Talldominerad skog (> 45 % tall)
  - Ljusgrön: Lövdominerad skog (> 45 % löv)
  - Olivgrön: Blandskog
  - Blå: Kalhyggen och ungskog (< 25 år eller < 35 m³sk/ha) – undvik dessa områden!
- **Markfuktighetslager (SLU DTW):** Visualisering av markens fuktighet från blöt sankmark till torr hällmark.
- **Punktinspektion i Fält:** Klicka var som helst på kartan för att få en ögonblicklig analys:
  - Total sannolikhetspoäng (t.ex. 80 % Hotspot).
  - Skogstyp och fördelning mellan Gran, Tall och Löv (m³sk/ha och procent).
  - Skogens uppskattade beståndsålder i år.
  - Markfuktighetsklass enligt SLU DTW.
  - Detaljerad ekologisk motivering varför platsen är lämplig eller olämplig.
- **Mina Sparade Ställen:** Spara dina egna svampfynd med titel, svampart, mängd, datum, anteckningar och koordinater i en lokal SQLite-databas.
  - Filtrera kartan till att visa och fokusera på ett specifikt sparat ställe.
  - Toggla sparade ställen av och på i lagermenyn.
- **Smart Navigering:** Klicka på "Navigera" för att öppna platsen som en nål i Google Maps så att du i lugn och ro kan granska rutten och välja när du startar bil- eller gångvägledningen.
- **Teaser för Gul Kantarell:** Förberett lagerval för Gul kantarell med förklarande dialog och information om kommande uppdatering.
- **100 % Offline-Kapacitet:** All svampdata, inspektionsraster och terrängkartor lagras lokalt på enheten via MBTiles och binärkomprimerade matriser.
- **Flerspråkigt Stöd:** Automatiskt stöd för både **svenska** och **engelska** baserat på telefonens systemspråk.

---

## Områdestäckning / Supported Areas

Systemets skogliga beräkningsmodeller och rasterlager täcker följande kommuner och städer:
- **Ale kommun**
- **Lilla Edet kommun**
- **Göteborg** (Gothenburg)
- **Lidköping**
- **Marks kommun**

> [!NOTE]
> Hotspot-modellen och punktinspektionen är kalibrerade för ovanstående kommuner. Vid klick utanför detta område visas standardbaskartan, med meddelande om att lokal skogsdata saknas.

---

## Geodata & Källor

Systemet bygger på officiella, öppna svenska geodatakällor av högsta vetenskapliga standard:

### 1. Skogliga Grunddata (SLU Skogsdatalabbet & Skogsstyrelsen)
Data framställd genom sambearbetning av Lantmäteriets nationella laserskanning (LiDAR) och Riksskogstaxeringens provytor.
- **Trädslagsfördelning (Raster, 12.5 m upplösning):**
  - `GranVol`: Volym gran i m³sk/ha (kubikmeter skog per hektar).
  - `TallVol`: Volym tall i m³sk/ha.
  - `LovVol`: Volym lövträd i m³sk/ha.
- **Beståndsålder (Raster, 12.5 m upplösning):**
  - `alder_gran`: Trädens genomsnittsålder i grandominerad skog.
  - `alder_blandskog`: Trädens genomsnittsålder i blandad skog.

### 2. Markfuktighetskartan (SLU DTW – Depth to Water)
Hydrografiskt anpassad digital höjdmodell (DEM) beräknad med SLU:s markfuktighetsalgoritm:
- `Klass 0`: Vatten och oklassificerad mark.
- `Klass 1`: Blöt mark / sankmark (grundvattenyta 0–1 meter under markytan).
- `Klass 2`: Fuktig mark (grundvattenyta 1–2 meter under markytan).
- `Klass 3`: Frisk mark (grundvattenyta 2–4 meter under markytan).
- `Klass 4`: Torr mark / hällmark (> 4 meter till grundvattenytan).

### 3. Maskning & Vektorgränser (Lantmäteriet & OSM)
- **Kommunpolygoner (Lantmäteriet):** Ale och Lilla Edet kommuner (SWEREF99 TM / EPSG:3006).
- **Infrastruktur & Exploatering (OpenStreetMap):** Bebyggelse, vägar, industriområden och järnvägar buffrades och maskades bort för att utesluta trädgårdar, vägkanter och bebyggda områden.

### 4. Baskartor
- **Satellit:** ESRI World Imagery (högupplösta ortofoton).
- **Liberty:** OpenFreeMap / MapLibre vektorstilar baserade på OpenStreetMap.
- **Positron:** Ljus, minimalistisk vektorstil från OpenFreeMap.
- **OpenTopoMap:** Topografisk offline-fallback förpackad i MBTiles för Ale och Lilla Edet.

---

## Geoprocessering & Pipeline (GDAL)

Bearbetningspipelinen körs via automatiserade Python-skript och GDAL. Hela kedjan finns i mappen `/geodata`.

```
                  +-----------------------------------+
                  |   SLU Skogliga Grunddata (LiDAR)  |
                  |     - GranVol, TallVol, LovVol    |
                  |     - Alder Gran, Alder Bland     |
                  +-----------------+-----------------+
                                    |
+--------------------------+        |        +-------------------------+
|   SLU Markfuktighet      |        |        |  Lantmäteriet Kommuner  |
|         (DTW)            |        |        |    Ale & Lilla Edet     |
+------------+-------------+        |        +------------+------------+
             |                      |                     |
             +----------------------+---------------------+
                                    |
                           [ gdalwarp Klippning ]
                                    |
                  +-----------------+-----------------+
                  |                                   |
       [ process_hotspots_v6.py ]            [ process_skogstyp.py ]
                  |                                   |
          (Habitatmodellering                 (Klassificering av
          & GDAL SieveFilter)                 trädslag & hyggen)
                  |                                   |
                  +-----------------+-----------------+
                                    |
                           [ gdaldem & gdalwarp ]
                          (Färgläggning & EPSG:3857)
                                    |
                  +-----------------+-----------------+
                  |                                   |
       [ MBTiles-generering ]              [ create_inspection_grid.py ]
        (Raster kakel 10-14)                (Kompakt binärmatris 25m)
                  |                                   |
                  v                                   v
             *.mbtiles                       forest_inspection.bin
                  \                                   /
                   +----------------+----------------+
                                    |
                             [ Android App ]
```

### Steg-för-steg:

1. **Klippning och normalisering mot kommunpolygoner:**
   Rastren klipps med `gdalwarp` mot `ale_lilla_edet_sweref.geojson` med projicerat koordinatsystem SWEREF99 TM (EPSG:3006). Negativa värden och NoData sätts strikt till 0.

2. **Klassificering av Skogstyp (`process_skogstyp.py`):**
   - Skapar en 8-bitars rasterfil där varje pixel tilldelas en klass:
     - `1`: Kalhygge/Ungskog (ålder 1–25 år eller virkesförråd 5–35 m³sk/ha med låg ålder).
     - `2`: Grandominerad skog (granandel $\ge$ 45 %).
     - `3`: Talldominerad skog (tallandel $\ge$ 45 % och tall > gran).
     - `4`: Lövdominerad skog (lövandel $\ge$ 45 % och löv > barr).
     - `5`: Blandskog (etablerad skog med blandade arter).

3. **Habitatberäkning Trattkantarell (`process_hotspots_v6.py`):**
   - Identifierar kandidatytor enligt de ekologiska tröskelvärdena.
   - Kör `gdal.SieveFilter` med storlek 20 pixlar och 8-grannars konnektivitet för att filtrera bort isolerade små dungar, åkerholmar och dikesrenar under 0.3 hektar.

4. **Färgläggning och Omprojicering till Web Mercator (EPSG:3857):**
   - `gdaldem color-relief` applicerar färgpaletter (`color_tratt.txt`, `color_skogstyp.txt`, `color_fukt.txt`) med full alfakanal för transparens.
   - `gdalwarp -t_srs EPSG:3857 -r near` transformerar kartorna till standard Web Mercator utan att interpolera bort klassgränserna.

5. **Paketering till MBTiles och Binärgrid:**
   - Rastren paketeras till MBTiles i zoomnivåer 10–14.
   - `create_inspection_grid.py` resamplar alla grundlager till ett synkroniserat 25-meters rutnät och exporterar `forest_inspection.bin`.

---

## Ekologisk Algoritm & Habitatmodellering

### Biologiska Förutsättningar för Trattkantarell (*Craterellus tubaeformis*)
Trattkantarellen är en mykorrhizasvamp som bildar obligat symbios med barrträd. Den trivs framförallt i fuktiga, mossrika barr- och blandskogsmiljöer (ofta tillsammans med husmossa och väggmossa) där mikroklimatet är stabilt och fuktigt.

### Algoritmregler (Version 6.0)

En pixel betraktas som giltigt kandidathabitat om och endast om samtliga följande grundkrav uppfylls:

1. **Slutenhet och Virkesförråd:**
   $$\text{Totalvolym} = \text{Gran} + \text{Tall} + \text{Löv} \ge 150 \text{ m}^3\text{sk/ha}$$
   Maximal volym är satt till 600 m³sk/ha för att utesluta extremt tät ogenomtränglig industriskog.
2. **Närvaro av Symbiospartner (Barrträd):**
   $$\text{Barrvolym} = \text{Gran} + \text{Tall} \ge 70 \text{ m}^3\text{sk/ha}$$
   Svampen kan inte etablera sig i ren lövskog.
3. **Skoglig Kontinuitet & Beståndsålder:**
   $$\text{Maximal ålder} \ge 50 \text{ år}$$
   Ungskog och kalhyggen har förstört mycelet och saknar det etablerade mosskikt som trattkantarellen kräver.
4. **Markfuktighet (DTW):**
   $$\text{Fuktighet} \in \{2, 3\} \quad (\text{Fuktig mark eller Frisk mark})$$
   Blöt sankmark (Klass 1) och torr hällmark (Klass 4) utesluts helt.
5. **Arealfilter (Sieve Filter):**
   Kluster mindre än 20 pixlar (< ca 0.31 hektar) rensas bort för att garantera att endast reella skogspartier markeras.

### Poängsättning (Probability Score)

För pixlar som uppfyller grundkraven tilldelas en baspoäng samt ackumulerade bonusar upp till 100 %:

$$\text{Score} = 40\% \text{ (Baspoäng vid godkänt habitat)}$$
$$+ 20\% \text{ om Granvolym} \ge 100 \text{ m}^3\text{sk/ha (Gran är primär värdart)}$$
$$+ 20\% \text{ om Markfuktighet} = 2 \text{ (Perfekt fuktig mark)}$$
$$+ 20\% \text{ om Beståndsålder} \ge 70 \text{ år (Gammelskogsbonus med intakt mossa)}$$

| Sannolikhetspoäng | Klassificering | Kartfärg |
| :--- | :--- | :--- |
| **80 – 100 %** | Exceptionell Hotspot | Mörklila / Magenta |
| **60 – 79 %** | Mycket bra habitat | Lila |
| **40 – 59 %** | Bra habitat | Ljuslila |
| **0 – 39 %** | Ej hotspot / Olämpligt | Transparent |

---

## Applikationsarkitektur & Teknik

Appen är byggd med en modern, reaktiv Android-arkitektur i 100 % Kotlin.

```
                    +--------------------------------+
                    |          MainActivity          |
                    +---------------+----------------+
                                    |
         +--------------------------+--------------------------+
         |                          |                          |
+--------v-------+          +-------v--------+         +-------v--------+
|   MapScreen    |          | SavedSpots     |         | SettingsScreen |
|  (MapLibre)    |          |    Screen      |         |  (Inställn.)   |
+--------+-------+          +-------+--------+         +----------------+
         |                          |
         +-------------+------------+
                       |
     +-----------------+-----------------+
     |                                   |
+----v--------------------+     +--------v----------------+
|  ForestDataInspector    |     |  SavedSpotRepository    |
| (Memory-Mapped Binär)   |     |    (SQLite Databas)     |
|   forest_inspection.bin |     |      saved_spots.db     |
+-------------------------+     +-------------------------+
     |
+----v--------------------+
|   MBTilesTileSource     |
| (Lokal NanoHTTPD Server)|
|     Port 8080-8090      |
+-------------------------+
```

### 1. MapLibre Android SDK & Lokal MBTiles-Server
För att kringgå begränsningar med MapLibres hantering av Android-specifika fil-URI:er och tillåta snabb rendering av flera samtidiga rasterlager, implementerar appen en inbäddad HTTP-server med **NanoHTTPD** (`MBTilesTileSource.kt`).
- Servern startar på en dynamisk lokal port (`http://127.0.0.1:<port>/tiles/{layer}/{z}/{x}/{y}.png`).
- Varje MBTiles-databas öppnas med SQLite och serverar PNG-kakel i realtid.
- Stöd för oberoende transparens och synlighet per lager (Hotspots, Skogstyp, Markfuktighet).

### 2. Blixtsnabb Offline-Punktinspektion (`ForestDataInspector.kt`)
Istället för tunga och långsamma GIS-anrop på enheten används en minnesmappad binärfil (`forest_inspection.bin`, 15.2 MB) som täcker hela Ale och Lilla Edet:
- **Header (48 bytes):** Magisk signatur `SVMP`, version, avgränsningskoordinater ($X_{min}, Y_{max}$ i EPSG:3857), antal rader/kolumner samt cellstorlek (~47.2 m).
- **Cellstruktur (6 bytes per cell):**
  1. `gran` (uint8: 0–255 m³sk/ha)
  2. `tall` (uint8: 0–255 m³sk/ha)
  3. `lov` (uint8: 0–255 m³sk/ha)
  4. `alder` (uint8: 0–250 år)
  5. `fukt` (uint8: 0–4 DTW klass)
  6. `score` (uint8: 0–100 % sannolikhet)
- **Spatial Smoothing:** När användaren klickar på kartan beräknas koordinaten till cellindex och läser ett $3 \times 3$ grannskap för att jämna ut mikrolokala mätfel och ge en representativ bild av skogsbeståndet.

### 3. Sparade Ställen (`SavedSpotRepository.kt`)
En ren SQLite-databas hanterar användarens egna markeringar:
- Fält: `id`, `title`, `mushroom_type`, `amount`, `note`, `date`, `latitude`, `longitude`.
- Reaktiv uppdatering mot UI via Kotlin Coroutines `StateFlow`.
- Interaktion: Klicka på ett sparat ställe i listan för att fokusera på det i kartan, eller öppna det i Google Maps.

### 4. Användargränssnitt (Jetpack Compose & Material 3)
- **Flytande Meny (LayerSelectionSheet):** Samlar alla kartval (Baskarta och temalager) på ett ställe.
- **Förklaringsdialoger:** Pedagogiska färgprover och tydliga beskrivningar för varje enskilt lager.
- **Inga Emojis:** Rent, professionellt gränssnitt med standardiserade Material Design-ikoner.

---

## Bygg- och Installationsguide

### Förutsättningar
- **Java Development Kit (JDK):** Version 17
- **Android SDK:** API Level 34 (Compile SDK), API Level 26 (Min SDK)
- **Android NDK & Build-tools:** Senaste stabila version

### Bygg instruktioner via terminalen

1. **Klona repot:**
   ```bash
   git clone git@github.com:joelolofsson/Svampst-llet.git
   cd Svampst-llet/SvampRadar
   ```

2. **Sätt JAVA_HOME (om du har JDK 17 i en specifik mapp):**
   ```bash
   export JAVA_HOME=/path/to/jdk-17
   export PATH=$JAVA_HOME/bin:$PATH
   ```

3. **Regionala Product Flavors & App Bundles (.aab) / APK:**
   Appen är uppdelad i Gradle-flavors så att man kan bygga kompakta regionala varianter eller en fullständig bundle med alla regioner:

   | Flavor | Täckningsområde | Release AAB (Bundle) | Release APK (arm64-v8a) |
   | :--- | :--- | :--- | :--- |
   | `goteborg` | Göteborg | **26 MB** | **31 MB** |
   | `lidkoping` | Lidköping | **26 MB** | **32 MB** |
   | `mark` | Marks kommun | **39 MB** | **45 MB** |
   | `aleLillaEdet` | Ale & Lilla Edet (inkl. offline OpenTopoMap) | **79 MB** | **84 MB** |
   | `full` | Alla 5 kommuner kombinerade | **146 MB** | **151 MB** |

4. **Bygg en specifik region (t.ex. Göteborg eller Mark):**
   ```bash
   # Bygg App Bundle (.aab) för Göteborg
   ./gradlew bundleGoteborgRelease

   # Bygg fristående Release APK för Marks kommun
   ./gradlew assembleMarkRelease
   ```

5. **Bygg alla regioner samtidigt:**
   ```bash
   ./gradlew bundleRelease assembleRelease
   ```
   Artefakterna genereras i:
   - App Bundles: `app/build/outputs/bundle/<flavor>Release/app-<flavor>-release.aab`
   - Release APKs: `app/build/outputs/apk/<flavor>/release/app-<flavor>-release.apk`

6. **Installera och starta på enhet via ADB (exempel Göteborg):**
   ```bash
   adb install -r app/build/outputs/apk/goteborg/release/app-goteborg-release.apk
   adb shell am start -n se.svampradar.app/.MainActivity
   ```

---

## Versionshantering & Git

Projektets officiella GitHub-repository:
**[git@github.com:joelolofsson/Svampst-llet.git](https://github.com:joelolofsson/Svampst-llet)**

### Filer som ingår i versionshanteringen:
- `/SvampRadar`: Hela Android Studio-projektet (Kotlin, Gradle, Resurser, Assets).
- `/geodata`: Alla Python-skript för habitatmodellering, GDAL-skript, färgkartor och inspektionsgeneratorer.
- `README.md`: Denna fullständiga systemdokumentation.

---

## Licens & Rättigheter
- **Skogliga data:** © Sveriges lantbruksuniversitet (SLU) & Skogsstyrelsen under Creative Commons Erkännande (CC BY).
- **Markfuktighetskartan:** © Sveriges lantbruksuniversitet (SLU) under CC BY.
- **Kartdata:** © OpenStreetMap bidragsgivare under ODbL, ESRI World Imagery.
- **Källkod:** MIT License.
