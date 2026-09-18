import json
import urllib.request
from osgeo import gdal, ogr, osr
import numpy as np
import os

print("1. Hämtar hus och vägar från OSM för att bygga en 50m säkerhetszon...")

overpass_url = "https://overpass-api.de/api/interpreter"
# Förenklad fråga för att undvika Timeout: Hämtar bara byggnader och lite större vägar (inga service-vägar eller uppfarter)
overpass_query = """
[out:json][timeout:180];
(
  way["building"](57.8,11.9,58.35,12.5);
  way["highway"~"motorway|trunk|primary|secondary|tertiary|residential"](57.8,11.9,58.35,12.5);
);
out geom;
"""

try:
    req = urllib.request.Request(overpass_url, data=overpass_query.encode('utf-8'), headers={'User-Agent': 'SvampRadar/2.0'})
    with urllib.request.urlopen(req) as response:
        osm_data = json.loads(response.read().decode('utf-8'))
    print(f"Hittade {len(osm_data['elements'])} vägar, hus och zoner.")
except Exception as e:
    print("Fel vid OSM:", e)
    exit(1)

# Spara till GeoJSON
geojson = {"type": "FeatureCollection", "features": []}
for el in osm_data["elements"]:
    if "geometry" not in el: continue
    coords = [[pt["lon"], pt["lat"]] for pt in el["geometry"]]
    
    geom_type = "LineString"
    if el.get("tags", {}).get("building") or el.get("tags", {}).get("landuse"):
        if len(coords) >= 4 and coords[0] == coords[-1]:
            geom_type = "Polygon"
            coords = [coords]
            
    geojson["features"].append({
        "type": "Feature",
        "geometry": {"type": geom_type, "coordinates": coords},
        "properties": {"exclude": 1}
    })

with open("osm_raw.geojson", "w") as f:
    json.dump(geojson, f)

print("2. Reprojicerar till SWEREF99 TM (EPSG:3006) för att kunna mäta meter...")
os.system("ogr2ogr -f GeoJSON -t_srs EPSG:3006 osm_sweref.geojson osm_raw.geojson")

print("3. Bygger 40 meter buffer (säkerhetszon) runt alla hus och vägar...")
# Vi använder GDAL/OGR i Python för att lägga på buffer
in_ds = ogr.Open("osm_sweref.geojson")
in_layer = in_ds.GetLayer()

# Skapa ny shapefile/geojson för den buffrade masken
out_driver = ogr.GetDriverByName("GeoJSON")
if os.path.exists("osm_buffered.geojson"): os.remove("osm_buffered.geojson")
out_ds = out_driver.CreateDataSource("osm_buffered.geojson")
out_layer = out_ds.CreateLayer("buffer", srs=in_layer.GetSpatialRef(), geom_type=ogr.wkbPolygon)

for feature in in_layer:
    geom = feature.GetGeometryRef()
    if geom is not None:
        # 40 meters buffer täcker hela villatomter och marginaler från vägar
        buffered_geom = geom.Buffer(40.0) 
        out_feat = ogr.Feature(out_layer.GetLayerDefn())
        out_feat.SetGeometry(buffered_geom)
        out_layer.CreateFeature(out_feat)

in_ds = None
out_ds = None

print("4. Läser in SLU Skogskarta för att rasterisera masken...")
gran_ds = gdal.Open("GranVol_ale_lilla_edet.tif")
x_size, y_size = gran_ds.RasterXSize, gran_ds.RasterYSize

mask_ds = gdal.GetDriverByName("MEM").Create("", x_size, y_size, 1, gdal.GDT_Byte)
mask_ds.SetGeoTransform(gran_ds.GetGeoTransform())
mask_ds.SetProjection(gran_ds.GetProjection())

vec_ds = ogr.Open("osm_buffered.geojson")
gdal.RasterizeLayer(mask_ds, [1], vec_ds.GetLayer(), burn_values=[1])
mask_arr = mask_ds.GetRasterBand(1).ReadAsArray()
print(f"Maskering klar! {np.count_nonzero(mask_arr)} pixlar raderas bort av buffern.")

print("5. Beräknar Hotspots v4 (Strikt skog + 40m Buffer)...")
gran = gran_ds.GetRasterBand(1).ReadAsArray()

fukt_ds = gdal.Open("markfuktighet_clipped.tif")
fukt = fukt_ds.GetRasterBand(1).ReadAsArray()

alder_ds = gdal.Open("alder_gran_clipped.tif")
alder = alder_ds.GetRasterBand(1).ReadAsArray()
alder_nodata = alder_ds.GetRasterBand(1).GetNoDataValue()

hotspot = np.zeros_like(gran, dtype=np.float32)

cond_gran = (gran >= 150) & (gran <= 450)
if alder_nodata is not None:
    cond_alder = (alder >= 50) & (alder != alder_nodata) & (alder < 250)
else:
    cond_alder = (alder >= 50) & (alder < 250)
cond_fukt = (fukt == 2) | (fukt == 3)
cond_mask = (mask_arr == 0)

valid = cond_gran & cond_alder & cond_fukt & cond_mask
print(f"Hittade {np.count_nonzero(valid)} totala hotspot-pixlar!")

hotspot[valid] = 0.5
hotspot[valid & (alder >= 70)] += 0.2
hotspot[valid & (fukt == 2)] += 0.2
hotspot[valid & (gran >= 200) & (gran <= 350)] += 0.1

out_ds_tif = gdal.GetDriverByName("GTiff").Create("hotspot_tratt_v4_raw.tif", x_size, y_size, 1, gdal.GDT_Float32)
out_ds_tif.SetGeoTransform(gran_ds.GetGeoTransform())
out_ds_tif.SetProjection(gran_ds.GetProjection())
out_ds_tif.GetRasterBand(1).WriteArray(hotspot)
out_ds_tif.GetRasterBand(1).SetNoDataValue(0)
out_ds_tif.FlushCache()

print("Klar med Algoritm v4!")
