import numpy as np
from osgeo import gdal

print("Startar Algoritm 6.0 (Blandskog & Tall-inkludering)...")

# Öppna Volym-data
def load_band(filename):
    ds = gdal.Open(filename)
    arr = ds.GetRasterBand(1).ReadAsArray()
    nodata = ds.GetRasterBand(1).GetNoDataValue()
    return arr, nodata, ds

gran, _, ref_ds = load_band("GranVol_ale_lilla_edet.tif")
x_size, y_size = ref_ds.RasterXSize, ref_ds.RasterYSize
geo_transform = ref_ds.GetGeoTransform()
projection = ref_ds.GetProjection()

tall, _, _ = load_band("TallVol_clipped.tif")
lov, _, _ = load_band("LovVol_clipped.tif")
fukt, _, _ = load_band("markfuktighet_clipped.tif")

alder_gran, ag_nodata, _ = load_band("alder_gran_clipped.tif")
alder_bland, ab_nodata, _ = load_band("alder_blandskog_clipped.tif")

# Rensa nodata för ålder (ofta 255)
ag_clean = np.where((alder_gran == ag_nodata) | (alder_gran > 250), 0, alder_gran)
ab_clean = np.where((alder_bland == ab_nodata) | (alder_bland > 250), 0, alder_bland)
max_alder = np.maximum(ag_clean, ab_clean)

# Byt ut NoData i volymer till 0
gran = np.where(gran < 0, 0, gran)
tall = np.where(tall < 0, 0, tall)
lov = np.where(lov < 0, 0, lov)
total_vol = gran + tall + lov
barr_vol = gran + tall

# REGLER FÖR BLANDSKOG OCH TALL:
# 1. Total trädvolym >= 150 m3/ha (Kräver fortfarande tät skog)
cond_vol = (total_vol >= 150) & (total_vol <= 600)
# 2. Måste ha ett inslag av barrträd (minst 70 m3/ha gran eller tall)
cond_barr = (barr_vol >= 70)
# 3. Ålder >= 50 år
cond_alder = (max_alder >= 50)
# 4. Rätt fuktighet
cond_fukt = (fukt == 2) | (fukt == 3)

valid = cond_vol & cond_barr & cond_alder & cond_fukt
print(f"Hittade {np.count_nonzero(valid)} pixlar innan yt-filtrering.")

# YT-FILTER (Rensa bort åkerholmar < 0.3 hektar)
print("Kör yt-filter för att ta bort ensamma dikesrenar...")
mem_drv = gdal.GetDriverByName('MEM')
tmp_ds = mem_drv.Create('', x_size, y_size, 1, gdal.GDT_Byte)
tmp_ds.GetRasterBand(1).WriteArray(valid.astype(np.uint8))
sieve_ds = mem_drv.Create('', x_size, y_size, 1, gdal.GDT_Byte)

gdal.SieveFilter(tmp_ds.GetRasterBand(1), None, sieve_ds.GetRasterBand(1), 20, 8)
valid_filtered = sieve_ds.GetRasterBand(1).ReadAsArray() > 0

print(f"Kvar efter yt-filtrering: {np.count_nonzero(valid_filtered)} pixlar. (Algoritm 5 hade 12 446)")

# Poängsättning (Gran ger mer bonus än Tall)
hotspot = np.zeros_like(gran, dtype=np.float32)
hotspot[valid_filtered] = 0.4
hotspot[valid_filtered & (gran >= 100)] += 0.2  # Gran-bonus
hotspot[valid_filtered & (fukt == 2)] += 0.2    # Perfekt fukt-bonus
hotspot[valid_filtered & (max_alder >= 70)] += 0.2 # Gammelskogs-bonus

out_ds = gdal.GetDriverByName("GTiff").Create("hotspot_tratt_v6_raw.tif", x_size, y_size, 1, gdal.GDT_Float32)
out_ds.SetGeoTransform(geo_transform)
out_ds.SetProjection(projection)
out_ds.GetRasterBand(1).WriteArray(hotspot)
out_ds.GetRasterBand(1).SetNoDataValue(0)
out_ds.FlushCache()

print("Klart! Sparat v6.")
