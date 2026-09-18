import numpy as np
from osgeo import gdal

print("Skapar Skogstyp & Kalhygge-karta...")

def load(filename):
    ds = gdal.Open(filename)
    arr = ds.GetRasterBand(1).ReadAsArray()
    arr = np.where(arr < 0, 0, arr)
    return arr, ds

gran, ref_ds = load("GranVol_ale_lilla_edet.tif")
tall, _ = load("TallVol_clipped.tif")
lov, _ = load("LovVol_clipped.tif")

alder_g, _ = load("alder_gran_clipped.tif")
alder_b, _ = load("alder_blandskog_clipped.tif")
alder_g = np.where(alder_g > 250, 0, alder_g)
alder_b = np.where(alder_b > 250, 0, alder_b)
max_alder = np.maximum(alder_g, alder_b)

total_vol = gran + tall + lov
x_size, y_size = ref_ds.RasterXSize, ref_ds.RasterYSize
geo_transform = ref_ds.GetGeoTransform()
projection = ref_ds.GetProjection()

# Klasser:
# 0 = Ingen skog / Bakgrund (transparent)
# 1 = Kalhygge / Ungskog (< 25 år eller mycket låg volym i skogsmark) -> BLÅ
# 2 = Grandominerad skog -> MÖRKGRÖN
# 3 = Talldominerad skog -> ORANGE / BÄRNSTEN
# 4 = Lövdominerad skog -> LJUSGRÖN
# 5 = Blandskog -> OLIVGRÖN

skogstyp = np.zeros_like(gran, dtype=np.uint8)

# Kalhygge / Ungskog: Finns trädmarkering men under 25 år, eller kalhygge med volym 5-35 m3
cond_hygge = ((max_alder > 0) & (max_alder < 25)) | ((total_vol >= 5) & (total_vol < 35) & (max_alder < 40))
skogstyp[cond_hygge] = 1

# Etablerad skog (volym >= 35)
cond_skog = (total_vol >= 35) & (~cond_hygge)

# Dominans:
p_gran = np.where(total_vol > 0, gran / total_vol, 0)
p_tall = np.where(total_vol > 0, tall / total_vol, 0)
p_lov = np.where(total_vol > 0, lov / total_vol, 0)

# Gran (> 45%)
skogstyp[cond_skog & (p_gran >= 0.45)] = 2
# Tall (> 45%)
skogstyp[cond_skog & (p_tall >= 0.45) & (p_tall > p_gran)] = 3
# Löv (> 45%)
skogstyp[cond_skog & (p_lov >= 0.45) & (p_lov > p_gran) & (p_lov > p_tall)] = 4
# Blandskog (övrig skog)
skogstyp[cond_skog & (skogstyp == 0)] = 5

# Spara raw tif
out_ds = gdal.GetDriverByName("GTiff").Create("skogstyp_raw.tif", x_size, y_size, 1, gdal.GDT_Byte)
out_ds.SetGeoTransform(geo_transform)
out_ds.SetProjection(projection)
out_ds.GetRasterBand(1).WriteArray(skogstyp)
out_ds.GetRasterBand(1).SetNoDataValue(0)
out_ds.FlushCache()

print("Klar med skogstyp_raw.tif!")
