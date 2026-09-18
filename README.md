# SvampRadar

SvampRadar är din ultimata app för att hitta svamp i skogen, med ett specifikt fokus på Trattkantarell och Gul kantarell. Med offline-stöd och detaljerade MBTiles-kartor kan du hitta de bästa svampplatserna även långt från mobiltäckning.

## Skärmdumpar
(Lägg till skärmdumpar här)

## Teknologi
- 100% Kotlin
- Jetpack Compose & Material 3
- MapLibre Android SDK för snabb och offline-vänlig kartvisning
- MBTiles via inbyggd lokal HTTP-server

## Bygginstruktioner
1. Klona repot
2. Öppna i Android Studio
3. Bygg med `./gradlew assembleDebug`
4. MBTiles-filer kopieras automatiskt eller behöver placeras i `/data/data/se.svampradar.app/files/` på enheten

## Datakällor & Attribuering
- **Kartdata:** OpenStreetMap bidragsgivare (ODbL)
- **Topografi:** OpenTopoMap (CC-BY-SA)
- **Hotspot-data:** Genererad via öppna skogsdata och maskininlärningsmodeller för habitat-klassificering.

## Hur man genererar hotspot-data
Hotspot-datan skapas genom att kombinera:
1. Skogsstyrelsens data om trädslag (björk/tall/gran-fördelning)
2. Höjddata och fuktighetsindex
3. Konvertering till GeoJSON via GDAL
4. Skapande av MBTiles med tippecanoe för optimerad rendering på mobila enheter

## Licens
MIT License
