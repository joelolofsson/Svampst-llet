import struct
import numpy as np
from osgeo import gdal

print("Skapar kompakt inspektions-grid för Android...")

# 1. Reprojicera alla lager till gemensam Web Mercator referens i 25m upplösning
# Ladda referensgränser från hotspot_tratt_v6_3857.tif
ref_ds = gdal.Open("hotspot_tratt_v6_3857.tif")
gt = ref_ds.GetGeoTransform()
# 2x nedskalning för optimal filstorlek (ca 25m)
cols = ref_ds.RasterXSize // 2
rows = ref_ds.RasterYSize // 2
x_min = gt[0]
x_max = gt[0] + ref_ds.RasterXSize * gt[1]
y_max = gt[3]
y_min = gt[3] + ref_ds.RasterYSize * gt[5]

cell_x = (x_max - x_min) / cols
cell_y = (y_max - y_min) / rows

print(f"Grid: {cols}x{rows}, cell storlek: {cell_x:.1f}m x {cell_y:.1f}m")

def resample_to_grid(src_file):
    out_ds = gdal.GetDriverByName('MEM').Create('', cols, rows, 1, gdal.GDT_Float32)
    out_ds.SetGeoTransform((x_min, cell_x, 0, y_max, 0, -cell_y))
    out_ds.SetProjection(ref_ds.GetProjection())
    gdal.ReprojectImage(gdal.Open(src_file), out_ds, None, None, gdal.GRA_NearestNeighbour)
    arr = out_ds.GetRasterBand(1).ReadAsArray()
    return np.nan_to_num(arr, nan=0.0)

print("Samplar Gran, Tall, Löv, Ålder, Fukt, Score...")
gran = np.clip(resample_to_grid("GranVol_ale_lilla_edet.tif"), 0, 255).astype(np.uint8)
tall = np.clip(resample_to_grid("TallVol_clipped.tif"), 0, 255).astype(np.uint8)
lov = np.clip(resample_to_grid("LovVol_clipped.tif"), 0, 255).astype(np.uint8)

alder_g = resample_to_grid("alder_gran_clipped.tif")
alder_b = resample_to_grid("alder_blandskog_clipped.tif")
alder_g = np.where(alder_g > 250, 0, alder_g)
alder_b = np.where(alder_b > 250, 0, alder_b)
alder = np.clip(np.maximum(alder_g, alder_b), 0, 255).astype(np.uint8)

fukt = np.clip(resample_to_grid("markfuktighet_clipped.tif"), 0, 4).astype(np.uint8)
score_arr = resample_to_grid("hotspot_tratt_v6_3857.tif")
score = np.clip(score_arr * 100, 0, 100).astype(np.uint8)

# Packa binärfil
# Header: 4s (SVMP), i (version=1), d (x_min), d (y_max), i (cols), i (rows), d (cell_x), d (cell_y)
header = struct.pack(">4si2d2i2d", b"SVMP", 1, x_min, y_max, cols, rows, cell_x, cell_y)

# Kombinera i en (rows, cols, 6) uint8 array
combined = np.stack([gran, tall, lov, alder, fukt, score], axis=-1)

with open("forest_inspection.bin", "wb") as f:
    f.write(header)
    f.write(combined.tobytes())

print(f"Klar! Skapade forest_inspection.bin ({len(header) + combined.nbytes} bytes)")
