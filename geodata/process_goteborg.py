#!/usr/bin/env python3
"""
Geodata processing script for Göteborg (Gothenburg).
Generates:
1. skogstyp_goteborg.mbtiles & skogstyp.mbtiles
2. hotspot_trattkantarell_goteborg.mbtiles & hotspot_trattkantarell.mbtiles
3. forest_inspection.bin
"""

import os
import subprocess
import struct
import numpy as np
from osgeo import gdal

gdal.UseExceptions()

print("--- Startar process_goteborg.py ---")

# 1. Läs in de klippta volymrastren
def load_band(filename):
    ds = gdal.Open(filename)
    arr = ds.GetRasterBand(1).ReadAsArray()
    arr = np.where((arr < 0) | (arr == 65535), 0, arr).astype(np.float32)
    return arr, ds

print("1. Läser in volymdata för Göteborg...")
gran, ref_ds = load_band("GranVol_goteborg.tif")
tall, _ = load_band("TallVol_goteborg.tif")
lov, _ = load_band("LovVol_goteborg.tif")

x_size = ref_ds.RasterXSize
y_size = ref_ds.RasterYSize
geo_transform = ref_ds.GetGeoTransform()
projection = ref_ds.GetProjection()

print(f"Raster storlek: {x_size}x{y_size}")

total_vol = gran + tall + lov
barr_vol = gran + tall

# Uppskatta ålder och fukt från volymen:
# - Ålder: Om total_vol < 10 -> age=5; om total_vol < 35 -> age=15 (ungskog/kalhygge);
#          om total_vol < 80 -> age=40; om total_vol < 150 -> age=65;
#          om total_vol >= 150 -> age=min(95, 65 + (total_vol - 150) // 10).
# - Fukt: Om total_vol >= 20 -> moisture=2; annars moisture=1. (0 om total_vol == 0)
age = np.zeros_like(total_vol, dtype=np.uint8)
cond_l10 = (total_vol > 0) & (total_vol < 10)
cond_l35 = (total_vol >= 10) & (total_vol < 35)
cond_l80 = (total_vol >= 35) & (total_vol < 80)
cond_l150 = (total_vol >= 80) & (total_vol < 150)
cond_ge150 = total_vol >= 150

age[cond_l10] = 5
age[cond_l35] = 15
age[cond_l80] = 40
age[cond_l150] = 65
age[cond_ge150] = np.minimum(95, 65 + ((total_vol[cond_ge150] - 150) // 10)).astype(np.uint8)

fukt = np.where(total_vol >= 20, 2, np.where(total_vol > 0, 1, 0)).astype(np.uint8)

# 2. Skogstyp
print("2. Klassificerar skogstyp...")
skogstyp = np.zeros_like(gran, dtype=np.uint8)

# Kalhygge / Ungskog (< 25 år eller mycket låg volym i skogsmark 5-35)
cond_hygge = ((age > 0) & (age < 25)) | ((total_vol >= 5) & (total_vol < 35))
skogstyp[cond_hygge] = 1

# Etablerad skog (volym >= 35)
cond_skog = (total_vol >= 35) & (~cond_hygge)

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

out_ds = gdal.GetDriverByName("GTiff").Create("skogstyp_goteborg_raw.tif", x_size, y_size, 1, gdal.GDT_Byte)
out_ds.SetGeoTransform(geo_transform)
out_ds.SetProjection(projection)
out_ds.GetRasterBand(1).WriteArray(skogstyp)
out_ds.GetRasterBand(1).SetNoDataValue(0)
out_ds.FlushCache()
out_ds = None
print("Skapade skogstyp_goteborg_raw.tif")

# 3. Trattkantarell Hotspots (Algoritm 6.0)
print("3. Beräknar trattkantarell hotspots...")
cond_vol = (total_vol >= 150) & (total_vol <= 600)
cond_barr = barr_vol >= 70
cond_alder = age >= 50
cond_fukt = (fukt == 2) | (fukt == 3)

valid = cond_vol & cond_barr & cond_alder & cond_fukt
print(f"Kandidatpixlar före silning: {np.count_nonzero(valid)}")

mem_drv = gdal.GetDriverByName('MEM')
tmp_ds = mem_drv.Create('', x_size, y_size, 1, gdal.GDT_Byte)
tmp_ds.GetRasterBand(1).WriteArray(valid.astype(np.uint8))
sieve_ds = mem_drv.Create('', x_size, y_size, 1, gdal.GDT_Byte)

gdal.SieveFilter(tmp_ds.GetRasterBand(1), None, sieve_ds.GetRasterBand(1), 20, 8)
valid_filtered = sieve_ds.GetRasterBand(1).ReadAsArray() > 0
print(f"Kvar efter silning (>= 20 pixlar): {np.count_nonzero(valid_filtered)}")

hotspot = np.zeros_like(gran, dtype=np.float32)
hotspot[valid_filtered] = 0.4
hotspot[valid_filtered & (gran >= 100)] += 0.2
hotspot[valid_filtered & (fukt == 2)] += 0.2
hotspot[valid_filtered & (age >= 70)] += 0.2

out_ds = gdal.GetDriverByName("GTiff").Create("hotspot_tratt_goteborg_raw.tif", x_size, y_size, 1, gdal.GDT_Float32)
out_ds.SetGeoTransform(geo_transform)
out_ds.SetProjection(projection)
out_ds.GetRasterBand(1).WriteArray(hotspot)
out_ds.GetRasterBand(1).SetNoDataValue(0)
out_ds.FlushCache()
out_ds = None
print("Skapade hotspot_tratt_goteborg_raw.tif")

# 4. Omprojicering till EPSG:3857 och färgläggning
print("4. Reprojicerar till EPSG:3857 och applicerar färgpaletter...")
env = os.environ.copy()

def run_cmd(cmd):
    print("Kör:", cmd)
    res = subprocess.run(cmd, shell=True, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.stdout:
        print(res.stdout.strip())
    if res.stderr:
        print(res.stderr.strip())

# Skogstyp
run_cmd("gdalwarp -overwrite -t_srs EPSG:3857 -r near skogstyp_goteborg_raw.tif skogstyp_goteborg_3857.tif")
run_cmd("gdaldem color-relief skogstyp_goteborg_3857.tif color_skogstyp.txt skogstyp_goteborg_colored.tif -alpha")
if os.path.exists("skogstyp_goteborg.mbtiles"):
    os.remove("skogstyp_goteborg.mbtiles")
run_cmd("gdal_translate -of MBTILES -co TILE_FORMAT=PNG skogstyp_goteborg_colored.tif skogstyp_goteborg.mbtiles")
run_cmd("gdaladdo -r nearest skogstyp_goteborg.mbtiles 2 4 8 16")

# Trattkantarell
run_cmd("gdalwarp -overwrite -t_srs EPSG:3857 -r near hotspot_tratt_goteborg_raw.tif hotspot_tratt_goteborg_3857.tif")
run_cmd("gdaldem color-relief hotspot_tratt_goteborg_3857.tif color_tratt.txt hotspot_tratt_goteborg_colored.tif -alpha")
if os.path.exists("hotspot_trattkantarell_goteborg.mbtiles"):
    os.remove("hotspot_trattkantarell_goteborg.mbtiles")
run_cmd("gdal_translate -of MBTILES -co TILE_FORMAT=PNG hotspot_tratt_goteborg_colored.tif hotspot_trattkantarell_goteborg.mbtiles")
run_cmd("gdaladdo -r nearest hotspot_trattkantarell_goteborg.mbtiles 2 4 8 16")

# 5. Skapa kompakt inspektions-grid (forest_inspection.bin)
print("5. Skapar forest_inspection.bin...")
ref_ds = gdal.Open("hotspot_tratt_goteborg_3857.tif")
gt = ref_ds.GetGeoTransform()
cols = ref_ds.RasterXSize // 2
rows = ref_ds.RasterYSize // 2
x_min = gt[0]
x_max = gt[0] + ref_ds.RasterXSize * gt[1]
y_max = gt[3]
y_min = gt[3] + ref_ds.RasterYSize * gt[5]

cell_x = (x_max - x_min) / cols
cell_y = (y_max - y_min) / rows

print(f"Grid: {cols}x{rows}, cellstorlek: {cell_x:.1f}m x {cell_y:.1f}m")

def resample_to_grid(src_file):
    src_ds = gdal.Open(src_file)
    out_ds = gdal.GetDriverByName('MEM').Create('', cols, rows, 1, gdal.GDT_Float32)
    out_ds.SetGeoTransform((x_min, cell_x, 0, y_max, 0, -cell_y))
    out_ds.SetProjection(ref_ds.GetProjection())
    gdal.ReprojectImage(src_ds, out_ds, None, None, gdal.GRA_NearestNeighbour)
    arr = out_ds.GetRasterBand(1).ReadAsArray()
    return np.nan_to_num(arr, nan=0.0)

gran_grid = np.clip(resample_to_grid("GranVol_goteborg.tif"), 0, 255).astype(np.uint8)
tall_grid = np.clip(resample_to_grid("TallVol_goteborg.tif"), 0, 255).astype(np.uint8)
lov_grid = np.clip(resample_to_grid("LovVol_goteborg.tif"), 0, 255).astype(np.uint8)

tot_grid = gran_grid.astype(int) + tall_grid.astype(int) + lov_grid.astype(int)

age_grid = np.zeros_like(tot_grid, dtype=np.uint8)
age_grid[(tot_grid > 0) & (tot_grid < 10)] = 5
age_grid[(tot_grid >= 10) & (tot_grid < 35)] = 15
age_grid[(tot_grid >= 35) & (tot_grid < 80)] = 40
age_grid[(tot_grid >= 80) & (tot_grid < 150)] = 65
c_ge = tot_grid >= 150
age_grid[c_ge] = np.minimum(95, 65 + ((tot_grid[c_ge] - 150) // 10)).astype(np.uint8)

fukt_grid = np.where(tot_grid >= 20, 2, np.where(tot_grid > 0, 1, 0)).astype(np.uint8)

score_arr = resample_to_grid("hotspot_tratt_goteborg_3857.tif")
score_grid = np.clip(score_arr * 100, 0, 100).astype(np.uint8)

header = struct.pack(">4si2d2i2d", b"SVMP", 1, x_min, y_max, cols, rows, cell_x, cell_y)
combined = np.stack([gran_grid, tall_grid, lov_grid, age_grid, fukt_grid, score_grid], axis=-1)

with open("forest_inspection_goteborg.bin", "wb") as f:
    f.write(header)
    f.write(combined.tobytes())

print(f"Skapade forest_inspection_goteborg.bin ({len(header) + combined.nbytes} bytes)")
print("--- Klart med Göteborg-geodata! ---")
