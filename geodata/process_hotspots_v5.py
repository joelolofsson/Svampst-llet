import numpy as np
from osgeo import gdal

print("Startar Algoritm 5.0 (Strikt + Yt-filter / Sammanhängande skog)...")

# Öppna data
gran_ds = gdal.Open("GranVol_ale_lilla_edet.tif")
gran = gran_ds.GetRasterBand(1).ReadAsArray()
x_size, y_size = gran_ds.RasterXSize, gran_ds.RasterYSize
geo_transform = gran_ds.GetGeoTransform()
projection = gran_ds.GetProjection()

fukt_ds = gdal.Open("markfuktighet_clipped.tif")
fukt = fukt_ds.GetRasterBand(1).ReadAsArray()
alder_ds = gdal.Open("alder_gran_clipped.tif")
alder = alder_ds.GetRasterBand(1).ReadAsArray()
alder_nodata = alder_ds.GetRasterBand(1).GetNoDataValue()

# Grundregler
cond_gran = (gran >= 150) & (gran <= 450)
if alder_nodata is not None:
    cond_alder = (alder >= 50) & (alder != alder_nodata) & (alder < 250)
else:
    cond_alder = (alder >= 50) & (alder < 250)
cond_fukt = (fukt == 2) | (fukt == 3)

valid = cond_gran & cond_alder & cond_fukt

print(f"Hittade {np.count_nonzero(valid)} pixlar innan yt-filtrering.")

# YT-FILTER MED GDAL (SieveFilter)
# Silar bort alla sammanhängande kluster som är mindre än 20 pixlar (~3000 m2)
print("Silar bort små kluster (åkerholmar) med GDAL SieveFilter...")
mem_drv = gdal.GetDriverByName('MEM')
tmp_ds = mem_drv.Create('', x_size, y_size, 1, gdal.GDT_Byte)
tmp_ds.GetRasterBand(1).WriteArray(valid.astype(np.uint8))
sieve_ds = mem_drv.Create('', x_size, y_size, 1, gdal.GDT_Byte)

gdal.SieveFilter(tmp_ds.GetRasterBand(1), None, sieve_ds.GetRasterBand(1), 20, 8)

valid_filtered = sieve_ds.GetRasterBand(1).ReadAsArray() > 0

print(f"Kvar efter yt-filtrering: {np.count_nonzero(valid_filtered)} pixlar. Raderade alla smådungar!")

# Skapa hotspot med poäng
hotspot = np.zeros_like(gran, dtype=np.float32)
hotspot[valid_filtered] = 0.5
hotspot[valid_filtered & (alder >= 70)] += 0.2
hotspot[valid_filtered & (fukt == 2)] += 0.2
hotspot[valid_filtered & (gran >= 200) & (gran <= 350)] += 0.1

out_ds = gdal.GetDriverByName("GTiff").Create("hotspot_tratt_v5_raw.tif", x_size, y_size, 1, gdal.GDT_Float32)
# Fixa projektion och bounding box direkt!
out_ds.SetGeoTransform(geo_transform)
out_ds.SetProjection(projection)
out_ds.GetRasterBand(1).WriteArray(hotspot)
out_ds.GetRasterBand(1).SetNoDataValue(0)
out_ds.FlushCache()

print("Klart! Sparat v5.")
