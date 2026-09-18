#!/usr/bin/env python3
"""
Geoprocessing pipeline for Marks kommun:
Generates:
1. skogstyp.mbtiles
2. hotspot_trattkantarell.mbtiles
3. forest_inspection.bin
and copies them to SvampRadar/app/src/mark/assets/
"""

import os
import shutil
import subprocess
import struct
import numpy as np
from osgeo import gdal

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

TARGET_ASSETS_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../SvampRadar/app/src/mark/assets"))
os.makedirs(TARGET_ASSETS_DIR, exist_ok=True)

print("=== Steg 1: Laddar volymdata för Mark ===")

def load_band(filename):
    ds = gdal.Open(filename)
    if ds is None:
        raise FileNotFoundError(f"Kunde inte öppna {filename}")
    arr = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
    arr = np.where(arr < 0, 0, arr)
    return arr, ds

gran, ref_ds = load_band("GranVol_mark.tif")
tall, _ = load_band("TallVol_mark.tif")
lov, _ = load_band("LovVol_mark.tif")

x_size = ref_ds.RasterXSize
y_size = ref_ds.RasterYSize
geo_transform = ref_ds.GetGeoTransform()
projection = ref_ds.GetProjection()

print(f"Rasterstorlek för Mark: {x_size}x{y_size}")

total_vol = gran + tall + lov
barr_vol = gran + tall

# Uppskatta ålder och fukt från volym:
# Ålder:
# Om total_vol < 10 -> age=5;
# om total_vol < 35 -> age=15 (ungskog/kalhygge);
# om total_vol < 80 -> age=40;
# om total_vol < 150 -> age=65;
# om total_vol >= 150 -> age=min(95, 65 + (total_vol - 150) // 10).
print("Uppskattar skogsålder och markfuktighet...")
age = np.zeros_like(total_vol, dtype=np.uint8)
cond_age5 = (total_vol > 0) & (total_vol < 10)
cond_age15 = (total_vol >= 10) & (total_vol < 35)
cond_age40 = (total_vol >= 35) & (total_vol < 80)
cond_age65 = (total_vol >= 80) & (total_vol < 150)
cond_age_old = total_vol >= 150

age[cond_age5] = 5
age[cond_age15] = 15
age[cond_age40] = 40
age[cond_age65] = 65
extra_age = np.minimum(30, (total_vol[cond_age_old] - 150) // 10)
age[cond_age_old] = (65 + extra_age).astype(np.uint8)

# Fukt:
# Om total_vol >= 20 -> moisture=2 (frisk-fuktig, optimal för trattkantarell); annars moisture=1.
# Om total_vol == 0 -> moisture=0 (ingen skog)
moisture = np.zeros_like(total_vol, dtype=np.uint8)
moisture[(total_vol > 0) & (total_vol < 20)] = 1
moisture[total_vol >= 20] = 2

# Spara temporära tif för ålder och fukt (används i inspektionsgrid)
def save_raster(filename, data, dtype, nodata=0):
    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(filename, x_size, y_size, 1, dtype)
    out_ds.SetGeoTransform(geo_transform)
    out_ds.SetProjection(projection)
    out_ds.GetRasterBand(1).WriteArray(data)
    out_ds.GetRasterBand(1).SetNoDataValue(nodata)
    out_ds.FlushCache()
    out_ds = None

save_raster("alder_mark.tif", age, gdal.GDT_Byte)
save_raster("fukt_mark.tif", moisture, gdal.GDT_Byte)

print("=== Steg 2: Klassificerar Skogstyp ===")
# Klasser:
# 0 = Ingen skog / Bakgrund (transparent)
# 1 = Kalhygge / Ungskog (< 25 år eller mycket låg volym i skogsmark) -> BLÅ
# 2 = Grandominerad skog -> MÖRKGRÖN
# 3 = Talldominerad skog -> ORANGE / BÄRNSTEN
# 4 = Lövdominerad skog -> LJUSGRÖN
# 5 = Blandskog -> OLIVGRÖN

cond_hygge = (total_vol >= 5) & (total_vol < 35)
cond_skog = (total_vol >= 35)

p_gran = np.zeros_like(gran)
p_tall = np.zeros_like(tall)
p_lov = np.zeros_like(lov)

pos_vol = total_vol > 0
p_gran[pos_vol] = gran[pos_vol] / total_vol[pos_vol]
p_tall[pos_vol] = tall[pos_vol] / total_vol[pos_vol]
p_lov[pos_vol] = lov[pos_vol] / total_vol[pos_vol]

skogstyp = np.zeros_like(gran, dtype=np.uint8)
skogstyp[cond_hygge] = 1
skogstyp[cond_skog & (p_gran >= 0.45)] = 2
skogstyp[cond_skog & (p_tall >= 0.45) & (p_tall > p_gran)] = 3
skogstyp[cond_skog & (p_lov >= 0.45) & (p_lov > p_gran) & (p_lov > p_tall)] = 4
skogstyp[cond_skog & (skogstyp == 0)] = 5

save_raster("skogstyp_mark_raw.tif", skogstyp, gdal.GDT_Byte)
print("Sparade skogstyp_mark_raw.tif")

print("=== Steg 3: Beräknar Trattkantarell Hotspots (Algoritm 6.0) ===")
# Habitatkrav:
# 1. Total trädvolym 150 - 600 m3/ha
# 2. Barrvolym >= 70 m3/ha
cond_vol = (total_vol >= 150) & (total_vol <= 600)
cond_barr = (barr_vol >= 70)
valid = cond_vol & cond_barr

print(f"Kandidatpixlar innan yt-filtrering: {np.count_nonzero(valid)}")

# Arealfilter (SieveFilter, 20 pixlar, 8 grannar)
mem_drv = gdal.GetDriverByName('MEM')
tmp_ds = mem_drv.Create('', x_size, y_size, 1, gdal.GDT_Byte)
tmp_ds.GetRasterBand(1).WriteArray(valid.astype(np.uint8))
sieve_ds = mem_drv.Create('', x_size, y_size, 1, gdal.GDT_Byte)

gdal.SieveFilter(tmp_ds.GetRasterBand(1), None, sieve_ds.GetRasterBand(1), 20, 8)
valid_filtered = sieve_ds.GetRasterBand(1).ReadAsArray() > 0

print(f"Kandidatpixlar efter yt-filtrering: {np.count_nonzero(valid_filtered)}")

# Poängsättning:
hotspot = np.zeros_like(gran, dtype=np.float32)
hotspot[valid_filtered] = 0.4
hotspot[valid_filtered & (gran >= 100)] += 0.2       # Gran-bonus
hotspot[valid_filtered & (moisture == 2)] += 0.2     # Perfekt fukt-bonus
hotspot[valid_filtered & (age >= 70)] += 0.2         # Gammelskogs-bonus

save_raster("hotspot_tratt_mark_raw.tif", hotspot, gdal.GDT_Float32)
print("Sparade hotspot_tratt_mark_raw.tif")

print("=== Steg 4: Omprojicering till EPSG:3857 och MBTiles-export ===")

def run_cmd(cmd):
    print(f"Kör: {cmd}")
    res = subprocess.run(cmd, shell=True, check=True, text=True, capture_output=True)
    if res.stdout:
        print(res.stdout)

# 4a. Skogstyp
run_cmd("gdalwarp -t_srs EPSG:3857 -r near -dstnodata 0 -overwrite skogstyp_mark_raw.tif skogstyp_mark_3857.tif")
run_cmd("gdaldem color-relief -alpha skogstyp_mark_3857.tif color_skogstyp.txt skogstyp_mark_colored.tif")
if os.path.exists("skogstyp_mark.mbtiles"):
    os.remove("skogstyp_mark.mbtiles")
run_cmd("gdal_translate -of MBTILES skogstyp_mark_colored.tif skogstyp_mark.mbtiles -co NAME=skogstyp -co DESCRIPTION=skogstyp -co TYPE=overlay -co TILE_FORMAT=PNG")
run_cmd("gdaladdo -r nearest skogstyp_mark.mbtiles 2 4 8 16")
print("Skapade skogstyp_mark.mbtiles")

# 4b. Trattkantarell
run_cmd("gdalwarp -t_srs EPSG:3857 -r near -dstnodata 0 -overwrite hotspot_tratt_mark_raw.tif hotspot_tratt_mark_3857.tif")
run_cmd("gdaldem color-relief -alpha hotspot_tratt_mark_3857.tif color_tratt.txt hotspot_tratt_mark_colored.tif")
if os.path.exists("hotspot_trattkantarell_mark.mbtiles"):
    os.remove("hotspot_trattkantarell_mark.mbtiles")
run_cmd("gdal_translate -of MBTILES hotspot_tratt_mark_colored.tif hotspot_trattkantarell_mark.mbtiles -co NAME=hotspot_trattkantarell -co DESCRIPTION=hotspot_trattkantarell -co TYPE=overlay -co TILE_FORMAT=PNG")
run_cmd("gdaladdo -r nearest hotspot_trattkantarell_mark.mbtiles 2 4 8 16")
print("Skapade hotspot_trattkantarell_mark.mbtiles")

print("=== Steg 5: Skapar kompakt inspektions-grid (forest_inspection.bin) ===")
ref_ds = gdal.Open("hotspot_tratt_mark_3857.tif")
gt = ref_ds.GetGeoTransform()
cols = ref_ds.RasterXSize // 2
rows = ref_ds.RasterYSize // 2
x_min = gt[0]
x_max = gt[0] + ref_ds.RasterXSize * gt[1]
y_max = gt[3]
y_min = gt[3] + ref_ds.RasterYSize * gt[5]

cell_x = (x_max - x_min) / cols
cell_y = (y_max - y_min) / rows

print(f"Mark Grid: {cols}x{rows}, cellstorlek: {cell_x:.2f}m x {cell_y:.2f}m")
print(f"Bounding Box: x_min={x_min:.2f}, y_max={y_max:.2f}")

def resample_to_grid(src_file):
    out_ds = gdal.GetDriverByName('MEM').Create('', cols, rows, 1, gdal.GDT_Float32)
    out_ds.SetGeoTransform((x_min, cell_x, 0, y_max, 0, -cell_y))
    out_ds.SetProjection(ref_ds.GetProjection())
    gdal.ReprojectImage(gdal.Open(src_file), out_ds, None, None, gdal.GRA_NearestNeighbour)
    arr = out_ds.GetRasterBand(1).ReadAsArray()
    return np.nan_to_num(arr, nan=0.0)

print("Samplar gran, tall, löv, ålder, fukt och score...")
gran_grid = np.clip(resample_to_grid("GranVol_mark.tif"), 0, 255).astype(np.uint8)
tall_grid = np.clip(resample_to_grid("TallVol_mark.tif"), 0, 255).astype(np.uint8)
lov_grid = np.clip(resample_to_grid("LovVol_mark.tif"), 0, 255).astype(np.uint8)
alder_grid = np.clip(resample_to_grid("alder_mark.tif"), 0, 255).astype(np.uint8)
fukt_grid = np.clip(resample_to_grid("fukt_mark.tif"), 0, 4).astype(np.uint8)
score_arr = resample_to_grid("hotspot_tratt_mark_3857.tif")
score_grid = np.clip(score_arr * 100, 0, 100).astype(np.uint8)

# Packa binärfil med header
header = struct.pack(">4si2d2i2d", b"SVMP", 1, x_min, y_max, cols, rows, cell_x, cell_y)
combined = np.stack([gran_grid, tall_grid, lov_grid, alder_grid, fukt_grid, score_grid], axis=-1)

bin_filename = "forest_inspection_mark.bin"
with open(bin_filename, "wb") as f:
    f.write(header)
    f.write(combined.tobytes())

file_size = os.path.getsize(bin_filename)
print(f"Skapade {bin_filename} ({file_size} bytes, ca {file_size / (1024*1024):.2f} MB)")

print("=== Steg 6: Kopierar filer till Mark assets ===")
dest_skog = os.path.join(TARGET_ASSETS_DIR, "skogstyp.mbtiles")
dest_tratt = os.path.join(TARGET_ASSETS_DIR, "hotspot_trattkantarell.mbtiles")
dest_bin = os.path.join(TARGET_ASSETS_DIR, "forest_inspection.bin")

shutil.copyfile("skogstyp_mark.mbtiles", dest_skog)
shutil.copyfile("hotspot_trattkantarell_mark.mbtiles", dest_tratt)
shutil.copyfile("forest_inspection_mark.bin", dest_bin)

print(f"Kopierade till: {dest_skog} ({os.path.getsize(dest_skog)} bytes)")
print(f"Kopierade till: {dest_tratt} ({os.path.getsize(dest_tratt)} bytes)")
print(f"Kopierade till: {dest_bin} ({os.path.getsize(dest_bin)} bytes)")
print("=== Hela Mark-processen är slutförd med framgång! ===")
