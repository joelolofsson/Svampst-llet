# Guide: Lokalisera svampområden i Lilla Edet & Ale med QGIS och AI

Denna guide är framtagen för att instruera dig (AI-assistenten/AGY) i hur du hjälper mig att bygga en lokal svampkarta över Lilla Edet och Ale kommun. Målet är att använda öppna geodata från Skogsstyrelsen och SLU, behandla dessa i QGIS, och skapa rasterlager som pekar ut optimala växtplatser för kantareller och trattkantareller.

---

## 1. Målsättning

Att skapa en lokal, fältanpassad karta som med hjälp av geografiska variabler identifierar skogspartier (10x10 meters upplösning) med störst statistisk sannolikhet för att hysa:
1. **Trattkantareller** (Gynnas ofta av äldre granskog, hög markfuktighet/nära till vatten, mossig terräng).
2. **Gula kantareller** (Gynnas ofta av blandskog, medelålders skog, väldränerad men ej snustorr mark, gärna sluttningar/stigar).

Arbetsområdet är strikt begränsat till: **Lilla Edet** och **Ale kommun** (Västra Götalands län).

---

## 2. Datan som ska hanteras

Följande datakällor ska användas. Du (AI) ska assistera med nedladdningslänkar, QGIS-kommandon och rasterkalkylator-logik för dessa.

### 2.1 Kommungränser (Vektor/Shapefile)
*   **Källa:** Lantmäteriet (via SCB eller öppna dataportaler).
*   **Syfte:** Används som mask för att klippa (Clip) tunga rasterfiler så att vi endast processar Lilla Edet och Ale. Detta är avgörande för prestandan på den lokala datorn.

### 2.2 Skogliga Grunddata (Raster/GeoTIFF)
*   **Källa:** Skogsstyrelsens Skogliga grunddata (eller SLU Skogskarta).
*   **Datatyper:**
    *   **Trädslag (Volym/Andel):** Gran, Tall, Lövträd.
    *   **Skogens ålder.**
    *   **Grundyta/Biomassa** (som en proxy för skogens täthet/ljusinsläpp).

### 2.3 Markfuktighetskarta (Raster/GeoTIFF)
*   **Källa:** SLU Markfuktighetskarta (DTW - Depth to Water).
*   **Syfte:** Identifiera fuktig mark (bra för trattkantareller) och undvika direkta sankmarker eller extremt torra hällmarker.

### 2.4 Terrängmodell / Höjddata (Valfritt men rekommenderat)
*   **Källa:** Lantmäteriets höjdmodell (DEM).
*   **Syfte:** Skapa lutningskartor (Slope) och väderstreck (Aspect) för att hitta väldränerade sluttningar för gula kantareller.

---

## 3. Din uppgift (Steg-för-steg assistans)

När vi arbetar vidare förväntar jag mig att du guidar mig genom följande QGIS-arbetsflöde. Om jag stöter på problem med ett specifikt steg, ska du ge felsökningstips för QGIS 3.x.

### Steg 1: Geodata-insamling & Baslinje
*   Du ska bistå med exakta URL:er eller instruktioner för var på SLU:s eller Skogsstyrelsens ftp/dataportaler jag hittar GeoTIFF-filerna för Västra Götaland.
*   Instruera hur jag lägger till kommungränserna i QGIS och filtrerar ut (Query Builder/Select by Expression) Lilla Edet och Ale.

### Steg 2: Preprocessering (Clip)
*   Ge mig QGIS-instruktionen (via Processing Toolbox eller GDAL) för att beskära alla nedladdade läns-rasterfiler mot min kommun-polygon (`Clip Raster by Mask Layer`).

### Steg 3: Datatransformation (Om nödvändigt)
*   Säkerställ att alla rasterlager använder samma koordinatsystem (SWEREF 99 TM) och har samma upplösning (pixelsize). Ge instruktioner för `Warp (Reproject)` om så behövs.

### Steg 4: Rasterkalkylatorn (Kärnalgoritmen)
*   **Här är din viktigaste uppgift.** Du ska formulera logiska uttryck för QGIS Raster Calculator (`Rasterkalkylator`).
*   **Exempel för Trattkantarell:** Ta fram formler som i pseudokod liknar: `OM (Gran > 60%) OCH (Ålder > 50 år) OCH (Markfuktighet == Fuktig) MAKA = Hotspot`.
*   **Exempel för Gul kantarell:** Ta fram formler för blandskog, medelålder och torrare mark.
*   Hjälp mig finjustera tröskelvärdena när vi ser resultatet.

### Steg 5: Visualisering
*   Instruera hur jag lägger på en färgskala (Symbology -> Singleband pseudocolor) på resultatet så att hotspot-områdena lyser rött eller gult, med genomskinlig bakgrund, överlagrat på en vanlig topografisk karta eller flygbild.

### Steg 6: Export till fältbruk
*   Jag kommer att använda appen **QField** i mobilen när jag är i skogen.
*   Ge mig stegen för att använda pluginet `QFieldSync` i QGIS för att paketera projektet och överföra det till min Android-enhet.

---

## 4. Arbetsmetodik

*   Vänta på mina prompter. Jag kommer att säga t.ex. *"Nu har jag klippt rasterfilerna. Vad blir formeln för trattkantareller i rasterkalkylatorn?"*.
*   Skriv alltid QGIS-uttryck i kodblock.
*   Håll det tekniskt och praktiskt. Anta att jag har grundläggande förståelse för filer och datorer, men behöver guidning i de specifika GIS-verktygen.
