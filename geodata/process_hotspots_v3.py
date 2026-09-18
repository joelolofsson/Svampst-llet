import numpy as np
from osgeo import gdal, ogr

print("Startar Algoritm 3.0 (STRICT)...")

# Öppna data
gran_ds = gdal.Open("GranVol_ale_lilla_edet.tif")
gran = gran_ds.GetRasterBand(1).ReadAsArray()
x_size = gran_ds.RasterXSize
y_size = gran_ds.RasterYSize
geo_transform = gran_ds.GetGeoTransform()
projection = gran_ds.GetProjection()

fukt_ds = gdal.Open("markfuktighet_clipped.tif")
fukt = fukt_ds.GetRasterBand(1).ReadAsArray()

alder_ds = gdal.Open("alder_gran_clipped.tif")
alder = alder_ds.GetRasterBand(1).ReadAsArray()

# Läs in NoData-värden
alder_nodata = alder_ds.GetRasterBand(1).GetNoDataValue()

# Rasterisera masken igen
print("Rasteriserar OSM mask...")
mask_ds = gdal.GetDriverByName("MEM").Create("", x_size, y_size, 1, gdal.GDT_Byte)
mask_ds.SetGeoTransform(geo_transform)
mask_ds.SetProjection(projection)

vec_ds = ogr.Open("exclude_mask_sweref_fixed.geojson")
layer = vec_ds.GetLayer()
gdal.RasterizeLayer(mask_ds, [1], layer, burn_values=[1])
mask = mask_ds.GetRasterBand(1).ReadAsArray()

print("Beräknar hotspot...")
hotspot = np.zeros_like(gran, dtype=np.float32)

# STRIKTA REGLER FÖR ATT ELIMINERA TRÄDGÅRDSGRANAR OCH KANTZONER:
# 1. Minst 150 m3/ha (Kräver en riktig, tät skog)
# 2. Max 450 m3/ha (Undvik bäcksvarta plantager)
cond_gran = (gran >= 150) & (gran <= 450)

# 3. Ålder >= 50 år (Säkerställer gammal, etablerad mossa). Filtrera bort NoData (ofta 255 eller <0)
if alder_nodata is not None:
    cond_alder = (alder >= 50) & (alder != alder_nodata) & (alder < 250)
else:
    cond_alder = (alder >= 50) & (alder < 250)

# 4. Fuktighet klass 2 eller 3
cond_fukt = (fukt == 2) | (fukt == 3)

# 5. Måste vara utanför stads-/åkermasken
cond_mask = (mask == 0)

# Kombinera allt
valid = cond_gran & cond_alder & cond_fukt & cond_mask
print(f"Hittade {np.count_nonzero(valid)} strikta hotspot-pixlar!")

hotspot[valid] = 0.5
hotspot[valid & (alder >= 70)] += 0.2
hotspot[valid & (fukt == 2)] += 0.2
hotspot[valid & (gran >= 200) & (gran <= 350)] += 0.1

out_ds = gdal.GetDriverByName("GTiff").Create("hotspot_tratt_v3_raw.tif", x_size, y_size, 1, gdal.GDT_Float32)
out_ds.SetGeoTransform(geo_transform)
out_ds.SetProjection(projection)
out_ds.GetRasterBand(1).WriteArray(hotspot)
out_ds.GetRasterBand(1).SetNoDataValue(0)
out_ds.FlushCache()

print("Klart! Sparat v3.")
