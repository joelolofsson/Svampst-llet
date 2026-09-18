#!/usr/bin/env python3
"""
Process Lidkoping geodata:
1. Classify skogstyp
2. Calculate hotspot trattkantarell with SieveFilter
3. Reproject to EPSG:3857 and colorize
4. Generate MBTiles (skogstyp.mbtiles, hotspot_trattkantarell.mbtiles) with overviews
5. Generate compact forest_inspection.bin
"""

import os
import sys
import subprocess
import struct
import numpy as np
from osgeo import gdal

gdal.UseExceptions()

WORKDIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORKDIR)

print("--- Steg 1 & 2: Laddar volymdata för Lidköping ---")

def load_raster(filename):
    ds = gdal.Open(filename)
    arr = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
    nodata = ds.GetRasterBand(1).GetNoDataValue()
    if nodata is not None:
        arr = np.where(arr == nodata, 0, arr)
    arr = np.where((arr < 0) | (arr > 2000), 0, arr)
    return arr, ds

gran, ref_ds = load_raster("GranVol_lidkoping.tif")
tall, _ = load_raster("TallVol_lidkoping.tif")
lov, _ = load_raster("LovVol_lidkoping.tif")

x_size = ref_ds.RasterXSize
y_size = ref_ds.RasterYSize
geo_transform = ref_ds.GetGeoTransform()
projection = ref_ds.GetProjection()

total_vol = gran + tall + lov
barr_vol = gran + tall

# Uppskatta ålder och fukt från volymen
# Ålder:
# Om total_vol < 10 -> age=5
# Om total_vol < 35 -> age=15 (ungskog/kalhygge)
# Om total_vol < 80 -> age=40
# Om total_vol < 150 -> age=65
# Om total_vol >= 150 -> age=min(95, 65 + (total_vol - 150) // 10)
age = np.zeros_like(total_vol, dtype=np.int32)
age[(total_vol > 0) & (total_vol < 10)] = 5
age[(total_vol >= 10) & (total_vol < 35)] = 15
age[(total_vol >= 35) & (total_vol < 80)] = 40
age[(total_vol >= 80) & (total_vol < 150)] = 65
c150 = total_vol >= 150
age[c150] = np.minimum(95, 65 + ((total_vol[c150] - 150) // 10).astype(np.int32))

# Fukt: Om total_vol >= 20 -> moisture=2 (frisk-fuktig, optimal); annars moisture=1
moisture = np.where(total_vol >= 20, 2, 1)

print("--- Skapar skogstyp ---")
# 0 = Ingen skog / Bakgrund (transparent)
# 1 = Kalhygge / Ungskog (< 25 år eller 5-35 m3)
# 2 = Grandominerad skog (> 45%)
# 3 = Talldominerad skog (> 45% och tall > gran)
# 4 = Lövdominerad skog (> 45% och löv > barr)
# 5 = Blandskog
skogstyp = np.zeros_like(gran, dtype=np.uint8)

cond_hygge = ((age > 0) & (age < 25)) | ((total_vol >= 5) & (total_vol < 35) & (age < 40))
skogstyp[cond_hygge] = 1

cond_skog = (total_vol >= 35) & (~cond_hygge)
p_gran = np.divide(gran, total_vol, out=np.zeros_like(gran), where=total_vol > 0)
p_tall = np.divide(tall, total_vol, out=np.zeros_like(tall), where=total_vol > 0)
p_lov = np.divide(lov, total_vol, out=np.zeros_like(lov), where=total_vol > 0)

skogstyp[cond_skog & (p_gran >= 0.45)] = 2
skogstyp[cond_skog & (p_tall >= 0.45) & (p_tall > p_gran)] = 3
skogstyp[cond_skog & (p_lov >= 0.45) & (p_lov > p_gran) & (p_lov > p_tall)] = 4
skogstyp[cond_skog & (skogstyp == 0)] = 5

out_skog = gdal.GetDriverByName("GTiff").Create("skogstyp_lidkoping_raw.tif", x_size, y_size, 1, gdal.GDT_Byte)
out_skog.SetGeoTransform(geo_transform)
out_skog.SetProjection(projection)
out_skog.GetRasterBand(1).WriteArray(skogstyp)
out_skog.GetRasterBand(1).SetNoDataValue(0)
out_skog.FlushCache()
out_skog = None
print("Sparat skogstyp_lidkoping_raw.tif")

print("--- Skapar hotspot trattkantarell (Algoritm 6.0) ---")
# 1. Total trädvolym >= 150 och <= 600
cond_vol = (total_vol >= 150) & (total_vol <= 600)
# 2. Barrvolym >= 70
cond_barr = (barr_vol >= 70)
# 3. Ålder >= 50
cond_alder = (age >= 50)
# 4. Rätt fuktighet (2 eller 3)
cond_fukt = (moisture == 2) | (moisture == 3)

valid = cond_vol & cond_barr & cond_alder & cond_fukt
print(f"Kandidatpixlar innan sieve: {np.count_nonzero(valid)}")

# SieveFilter (kluster >= 20 pixlar ~ 0.31 ha)
mem_drv = gdal.GetDriverByName('MEM')
tmp_ds = mem_drv.Create('', x_size, y_size, 1, gdal.GDT_Byte)
tmp_ds.GetRasterBand(1).WriteArray(valid.astype(np.uint8))
sieve_ds = mem_drv.Create('', x_size, y_size, 1, gdal.GDT_Byte)
gdal.SieveFilter(tmp_ds.GetRasterBand(1), None, sieve_ds.GetRasterBand(1), 20, 8)
valid_filtered = sieve_ds.GetRasterBand(1).ReadAsArray() > 0
print(f"Pixlar efter sieve: {np.count_nonzero(valid_filtered)}")

# Poängsättning:
# Baspoäng: 40%
# +20% om Granvolym >= 100
# +20% om Fuktighet == 2
# +20% om Ålder >= 70
hotspot = np.zeros_like(gran, dtype=np.float32)
hotspot[valid_filtered] = 0.4
hotspot[valid_filtered & (gran >= 100)] += 0.2
hotspot[valid_filtered & (moisture == 2)] += 0.2
hotspot[valid_filtered & (age >= 70)] += 0.2

out_hot = gdal.GetDriverByName("GTiff").Create("hotspot_tratt_lidkoping_raw.tif", x_size, y_size, 1, gdal.GDT_Float32)
out_hot.SetGeoTransform(geo_transform)
out_hot.SetProjection(projection)
out_hot.GetRasterBand(1).WriteArray(hotspot)
out_hot.GetRasterBand(1).SetNoDataValue(0)
out_hot.FlushCache()
out_hot = None
print("Sparat hotspot_tratt_lidkoping_raw.tif")

# Kör gdalwarp till EPSG:3857 och färglägg
def run_cmd(cmd):
    print(f"Kör: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

print("--- Omprojicerar till EPSG:3857 ---")
run_cmd("gdalwarp -overwrite -t_srs EPSG:3857 -r near skogstyp_lidkoping_raw.tif skogstyp_lidkoping_3857.tif")
run_cmd("gdalwarp -overwrite -t_srs EPSG:3857 -r near hotspot_tratt_lidkoping_raw.tif hotspot_tratt_lidkoping_3857.tif")

print("--- Färglägger raster med gdaldem color-relief ---")
run_cmd("gdaldem color-relief -alpha skogstyp_lidkoping_3857.tif color_skogstyp.txt skogstyp_lidkoping_colored.tif")
run_cmd("gdaldem color-relief -alpha hotspot_tratt_lidkoping_3857.tif color_tratt.txt hotspot_tratt_lidkoping_colored.tif")

print("--- Skapar MBTiles för Lidköping ---")
mbtiles_skog = "skogstyp_lidkoping.mbtiles"
mbtiles_hotspot = "hotspot_trattkantarell_lidkoping.mbtiles"

if os.path.exists(mbtiles_skog):
    os.remove(mbtiles_skog)
if os.path.exists(mbtiles_hotspot):
    os.remove(mbtiles_hotspot)

run_cmd(f"gdal_translate -of MBTILES -co NAME=skogstyp -co DESCRIPTION=skogstyp skogstyp_lidkoping_colored.tif {mbtiles_skog}")
run_cmd(f"gdaladdo -r nearest {mbtiles_skog} 2 4 8 16")

run_cmd(f"gdal_translate -of MBTILES -co NAME=hotspot_trattkantarell -co DESCRIPTION=hotspot_trattkantarell hotspot_tratt_lidkoping_colored.tif {mbtiles_hotspot}")
run_cmd(f"gdaladdo -r nearest {mbtiles_hotspot} 2 4 8 16")

print("--- Skapar forest_inspection.bin för Lidköping ---")
ref_3857 = gdal.Open("hotspot_tratt_lidkoping_3857.tif")
gt_3857 = ref_3857.GetGeoTransform()
cols = ref_3857.RasterXSize // 2
rows = ref_3857.RasterYSize // 2
x_min = gt_3857[0]
x_max = gt_3857[0] + ref_3857.RasterXSize * gt_3857[1]
y_max = gt_3857[3]
y_min = gt_3857[3] + ref_3857.RasterYSize * gt_3857[5]

cell_x = (x_max - x_min) / cols
cell_y = (y_max - y_min) / rows

print(f"Grid: {cols}x{rows}, cell storlek: {cell_x:.2f}m x {cell_y:.2f}m")
print(f"Område: xMin={x_min}, yMax={y_max}, xMax={x_max}, yMin={y_min}")

def resample_to_grid(src_file):
    out_ds = gdal.GetDriverByName('MEM').Create('', cols, rows, 1, gdal.GDT_Float32)
    out_ds.SetGeoTransform((x_min, cell_x, 0, y_max, 0, -cell_y))
    out_ds.SetProjection(ref_3857.GetProjection())
    gdal.ReprojectImage(gdal.Open(src_file), out_ds, None, None, gdal.GRA_NearestNeighbour)
    arr = out_ds.GetRasterBand(1).ReadAsArray()
    return np.nan_to_num(arr, nan=0.0)

gran_grid = np.clip(resample_to_grid("GranVol_lidkoping.tif"), 0, 255).astype(np.uint8)
tall_grid = np.clip(resample_to_grid("TallVol_lidkoping.tif"), 0, 255).astype(np.uint8)
lov_grid = np.clip(resample_to_grid("LovVol_lidkoping.tif"), 0, 255).astype(np.uint8)

total_grid = gran_grid.astype(np.int32) + tall_grid.astype(np.int32) + lov_grid.astype(np.int32)

age_grid = np.zeros_like(total_grid, dtype=np.uint8)
age_grid[(total_grid > 0) & (total_grid < 10)] = 5
age_grid[(total_grid >= 10) & (total_grid < 35)] = 15
age_grid[(total_grid >= 35) & (total_grid < 80)] = 40
age_grid[(total_grid >= 80) & (total_grid < 150)] = 65
c150_grid = total_grid >= 150
age_grid[c150_grid] = np.minimum(95, 65 + ((total_grid[c150_grid] - 150) // 10)).astype(np.uint8)

fukt_grid = np.where(total_grid >= 20, 2, 1).astype(np.uint8)
fukt_grid[total_grid == 0] = 0

score_arr = resample_to_grid("hotspot_tratt_lidkoping_3857.tif")
score_grid = np.clip(np.round(score_arr * 100), 0, 100).astype(np.uint8)

header = struct.pack(">4si2d2i2d", b"SVMP", 1, x_min, y_max, cols, rows, cell_x, cell_y)
combined = np.stack([gran_grid, tall_grid, lov_grid, age_grid, fukt_grid, score_grid], axis=-1)

bin_path = "forest_inspection_lidkoping.bin"
with open(bin_path, "wb") as f:
    f.write(header)
    f.write(combined.tobytes())

print(f"Sparade {bin_path} ({len(header) + combined.nbytes} bytes)")

# Kopiera till SvampRadar/app/src/lidkoping/assets/
assets_dir = os.path.abspath(os.path.join(WORKDIR, "../SvampRadar/app/src/lidkoping/assets"))
os.makedirs(assets_dir, exist_ok=True)
import shutil
shutil.copyfile(mbtiles_skog, os.path.join(assets_dir, "skogstyp.mbtiles"))
shutil.copyfile(mbtiles_hotspot, os.path.join(assets_dir, "hotspot_trattkantarell.mbtiles"))
shutil.copyfile(bin_path, os.path.join(assets_dir, "forest_inspection.bin"))
print(f"Kopierade filer till {assets_dir}!")

print("Hela geoprocesseringen för Lidköping är klar!")
