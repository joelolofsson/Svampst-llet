import json
import urllib.request
import urllib.parse
from osgeo import gdal, ogr, osr
import numpy as np
import os

# 1. Fetch OSM data for Ale and Lilla Edet (Landuse: residential, commercial, industrial, farmland, grass, etc)
print("Hämtar OSM data för exkludering (Bebyggelse, Åkermark etc)...")

overpass_url = "https://overpass-api.de/api/interpreter"
overpass_query = """
[out:json][timeout:120];
(
  way["landuse"~"residential|commercial|industrial|retail|farmland|farmyard|meadow|grass|cemetery|allotments"](57.8,11.9,58.35,12.5);
  way["leisure"~"park|pitch|golf_course|garden"](57.8,11.9,58.35,12.5);
  way["building"](57.8,11.9,58.35,12.5);
);
out geom;
"""

try:
    req = urllib.request.Request(overpass_url, data=overpass_query.encode('utf-8'), headers={'User-Agent': 'SvampRadar/1.0'})
    with urllib.request.urlopen(req) as response:
        osm_data = json.loads(response.read().decode('utf-8'))
    print(f"Hittade {len(osm_data['elements'])} polygoner att exkludera.")
    
    with open("osm_exclude.json", "w") as f:
        json.dump(osm_data, f)
except Exception as e:
    print("Fel vid hämtning av OSM:", e)
    exit(1)

# 2. Skapa GeoJSON från OSM data
geojson = {
    "type": "FeatureCollection",
    "features": []
}

for element in osm_data["elements"]:
    if element["type"] == "way" and "geometry" in element:
        coords = [[pt["lon"], pt["lat"]] for pt in element["geometry"]]
        if len(coords) >= 4 and coords[0] == coords[-1]: # Valid polygon
            geojson["features"].append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords]
                },
                "properties": {"exclude": 1}
            })

with open("exclude_mask.geojson", "w") as f:
    json.dump(geojson, f)

print("Skapade exclude_mask.geojson. Rasteriserar nu...")

# 3. Läs referensraster för att få utsträckning och upplösning
ref_ds = gdal.Open("GranVol_ale_lilla_edet.tif")
geo_transform = ref_ds.GetGeoTransform()
projection = ref_ds.GetProjection()
x_size = ref_ds.RasterXSize
y_size = ref_ds.RasterYSize

# Rasterisera OSM mask (Vi behöver konvertera EPSG:4326 till EPSG:3006 först)
os.system('ogr2ogr -f GeoJSON -t_srs EPSG:3006 exclude_mask_sweref.geojson exclude_mask.geojson')

mask_ds = gdal.GetDriverByName('MEM').Create('', x_size, y_size, 1, gdal.GDT_Byte)
mask_ds.SetGeoTransform(geo_transform)
mask_ds.SetProjection(projection)

vec_ds = ogr.Open("exclude_mask_sweref.geojson")
gdal.RasterizeLayer(mask_ds, [1], vec_ds.GetLayer(), burn_values=[1])

mask_array = mask_ds.GetRasterBand(1).ReadAsArray()
print("Mask rasteriserad.")

# 4. Läs in skogsdata
print("Läser in skogsdata...")
gran_vol_ds = gdal.Open("GranVol_ale_lilla_edet.tif")
gran_vol = gran_vol_ds.GetRasterBand(1).ReadAsArray()

fukt_ds = gdal.Open("markfuktighet_clipped.tif")
fukt = fukt_ds.GetRasterBand(1).ReadAsArray()

alder_ds = gdal.Open("alder_gran_clipped.tif")
alder = alder_ds.GetRasterBand(1).ReadAsArray()

# 5. BERÄKNA NYA HOTSPOTS (Trattkantarell 2.0)
print("Beräknar hotspot 2.0...")
# Krav:
# - Granvolym: mellan 50 och 400 m3/ha (inte snår, inte bäcksvart)
# - Ålder: över 40 år (inga ungskogar/kalhyggen)
# - Fuktighet: Klass 2 (frisk-fuktig) eller 3 (fuktig-blöt). Inte 4 (vatten)
# - Mask: 0 (Ligger inte på åker/stad/park/tomt)

hotspot = np.zeros_like(gran_vol, dtype=np.float32)

# Vektoriserade villkor
cond_gran = (gran_vol >= 50) & (gran_vol <= 400)
cond_alder = (alder >= 40)
cond_fukt = (fukt == 2) | (fukt == 3)
cond_mask = (mask_array == 0)

# Kombinera
valid_pixels = cond_gran & cond_alder & cond_fukt & cond_mask

# Scora dem (1.0 = perfekt). Vi ger lite högre poäng om åldern är hög och volymen lagom.
hotspot[valid_pixels] = 0.5 # Baspoäng
hotspot[valid_pixels & (alder >= 60)] += 0.2 # Gammelskog bonus
hotspot[valid_pixels & (fukt == 2)] += 0.2 # Mesisk-fuktig är bäst
hotspot[valid_pixels & (gran_vol >= 100) & (gran_vol <= 300)] += 0.1 # Perfekt krontäckning

# Spara TIF
driver = gdal.GetDriverByName('GTiff')
out_ds = driver.Create('hotspot_tratt_v2_raw.tif', x_size, y_size, 1, gdal.GDT_Float32)
out_ds.SetGeoTransform(geo_transform)
out_ds.SetProjection(projection)
out_ds.GetRasterBand(1).WriteArray(hotspot)
out_ds.GetRasterBand(1).SetNoDataValue(0)
out_ds.FlushCache()

print("Klar! Sparade hotspot_tratt_v2_raw.tif")
