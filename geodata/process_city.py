#!/usr/bin/env python3
"""
Generalized Geodata processing script for ANY city.
Usage: python process_city.py <CityName> <FlavorName>
Example: python process_city.py Göteborg goteborg
"""

import os
import sys
import subprocess
import struct
import numpy as np
from osgeo import gdal, ogr, osr

gdal.UseExceptions()

if len(sys.argv) < 3:
    print("Usage: python process_city.py <CityName> <FlavorName>")
    print("Example: python process_city.py Göteborg goteborg")
    sys.exit(1)

city_name = sys.argv[1]
flavor_name = sys.argv[2]

print(f"--- Startar process_city.py för {city_name} (Flavor: {flavor_name}) ---")

# Files
geojson_src = "kommuner.geojson"
nmd_src = "NMD2023_basskikt_v2_1/NMD2023bas_v2_1.tif"
vol_files = {
    "gran": "GranVol_leaf.tif",
    "tall": "TallVol_leaf.tif",
    "lov": "LovVol_leaf.tif"
}

if not os.path.exists(nmd_src):
    print(f"FEL: Saknar {nmd_src}. Vänligen kör download_nmd.py först.")
    sys.exit(1)

# Paths for outputs
city_wgs84 = f"{flavor_name}_wgs84.geojson"
city_sweref = f"{flavor_name}_sweref.geojson"

def run_cmd(cmd):
    print("Kör:", cmd)
    res = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.stdout: print(res.stdout.strip())
    if res.stderr: print(res.stderr.strip())

# 1. Klipp ut staden/städerna från GeoJSON
print(f"1. Extraherar {city_name} från {geojson_src}...")

if "," in city_name:
    cities = [c.strip() for c in city_name.split(",")]
    where_clause = " OR ".join([f"kom_namn = '{c}'" for c in cities])
else:
    where_clause = f"kom_namn = '{city_name}'"

if os.path.exists(city_wgs84): os.remove(city_wgs84)
run_cmd(f'ogr2ogr -f GeoJSON -where "{where_clause}" {city_wgs84} {geojson_src}')

if os.path.exists(city_sweref): os.remove(city_sweref)
run_cmd(f'ogr2ogr -f GeoJSON -t_srs EPSG:3006 {city_sweref} {city_wgs84}')

# 2. Klipp volymrastren
print("2. Klipper volymraster...")
clipped_vols = {}
for name, src_file in vol_files.items():
    out_file = f"{name}Vol_{flavor_name}.tif"
    if not os.path.exists(out_file):
        run_cmd(f"gdalwarp -cutline {city_sweref} -crop_to_cutline -dstnodata 0 {src_file} {out_file}")
    clipped_vols[name] = out_file

# 3. Klipp NMD2023 så den EXAKT matchar GranVol_city (samma grid/extent/upplösning)
print("3. Klipper NMD2023-mask och anpassar grid...")
nmd_city = f"nmd_{flavor_name}.tif"
gran_ds = gdal.Open(clipped_vols["gran"])
gt = gran_ds.GetGeoTransform()
cols = gran_ds.RasterXSize
rows = gran_ds.RasterYSize
xmin = gt[0]
ymax = gt[3]
xmax = xmin + cols * gt[1]
ymin = ymax + rows * gt[5]

if not os.path.exists(nmd_city):
    run_cmd(f"gdalwarp -te {xmin} {ymin} {xmax} {ymax} -ts {cols} {rows} -r near {nmd_src} {nmd_city}")

# 4. Läs in arrayer och maska
print("4. Beräknar ålder, fukt och skogstyp (med NMD-mask)...")
def load_band(filename):
    ds = gdal.Open(filename)
    arr = ds.GetRasterBand(1).ReadAsArray()
    return np.where((arr < 0) | (arr == 65535), 0, arr).astype(np.float32)

gran = load_band(clipped_vols["gran"])
tall = load_band(clipped_vols["tall"])
lov = load_band(clipped_vols["lov"])
nmd_ds = gdal.Open(nmd_city)
nmd = nmd_ds.GetRasterBand(1).ReadAsArray()

total_vol = gran + tall + lov
barr_vol = gran + tall

# NMD Mask: 50-59 är Bebyggelse/Infrastruktur, 60-69 är Vatten. 
# Vi nollställer volym på all urban/vatten-yta!
urban_or_water = (nmd >= 50) & (nmd <= 69)
total_vol[urban_or_water] = 0
gran[urban_or_water] = 0
tall[urban_or_water] = 0
lov[urban_or_water] = 0
barr_vol[urban_or_water] = 0

# Syntetisera ålder och fukt (nu renons från villaträdgårdar!)
age = np.zeros_like(total_vol, dtype=np.uint8)
age[(total_vol > 0) & (total_vol < 10)] = 5
age[(total_vol >= 10) & (total_vol < 35)] = 15
age[(total_vol >= 35) & (total_vol < 80)] = 40
age[(total_vol >= 80) & (total_vol < 150)] = 65
c_ge = total_vol >= 150
age[c_ge] = np.minimum(95, 65 + ((total_vol[c_ge] - 150) // 10)).astype(np.uint8)

fukt = np.where(total_vol >= 20, 2, np.where(total_vol > 0, 1, 0)).astype(np.uint8)

# Skogstyp
skogstyp = np.zeros_like(gran, dtype=np.uint8)
cond_hygge = ((age > 0) & (age < 25)) | ((total_vol >= 5) & (total_vol < 35))
skogstyp[cond_hygge] = 1

cond_skog = (total_vol >= 35) & (~cond_hygge)
p_gran = np.where(total_vol > 0, gran / total_vol, 0)
p_tall = np.where(total_vol > 0, tall / total_vol, 0)
p_lov = np.where(total_vol > 0, lov / total_vol, 0)

skogstyp[cond_skog & (p_gran >= 0.45)] = 2
skogstyp[cond_skog & (p_tall >= 0.45) & (p_tall > p_gran)] = 3
skogstyp[cond_skog & (p_lov >= 0.45) & (p_lov > p_gran) & (p_lov > p_tall)] = 4
skogstyp[cond_skog & (skogstyp == 0)] = 5

def save_tif(filename, array, dtype=gdal.GDT_Byte, no_data=0):
    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(filename, cols, rows, 1, dtype)
    ds.SetGeoTransform(gt)
    ds.SetProjection(gran_ds.GetProjection())
    b = ds.GetRasterBand(1)
    b.WriteArray(array)
    b.SetNoDataValue(no_data)
    ds.FlushCache()

save_tif(f"skogstyp_{flavor_name}_raw.tif", skogstyp)

# 5. Hotspots
print("5. Beräknar hotspots...")
cond_vol = (total_vol >= 150) & (total_vol <= 600)
cond_barr = barr_vol >= 70
cond_alder = age >= 50
cond_fukt = (fukt == 2) | (fukt == 3)

valid = cond_vol & cond_barr & cond_alder & cond_fukt

mem_drv = gdal.GetDriverByName('MEM')
tmp_ds = mem_drv.Create('', cols, rows, 1, gdal.GDT_Byte)
tmp_ds.GetRasterBand(1).WriteArray(valid.astype(np.uint8))
sieve_ds = mem_drv.Create('', cols, rows, 1, gdal.GDT_Byte)

gdal.SieveFilter(tmp_ds.GetRasterBand(1), None, sieve_ds.GetRasterBand(1), 20, 8)
valid_filtered = sieve_ds.GetRasterBand(1).ReadAsArray() > 0

hotspot = np.zeros_like(gran, dtype=np.float32)
hotspot[valid_filtered] = 0.4
hotspot[valid_filtered & (gran >= 100)] += 0.2
hotspot[valid_filtered & (fukt == 2)] += 0.2
hotspot[valid_filtered & (age >= 70)] += 0.2

save_tif(f"hotspot_{flavor_name}_raw.tif", hotspot, gdal.GDT_Float32)

# 6. Exportera till MBTiles och kopiera till Android app
print("6. Reprojicerar och skapar MBTiles...")
run_cmd(f"gdalwarp -overwrite -t_srs EPSG:3857 -r near skogstyp_{flavor_name}_raw.tif skogstyp_{flavor_name}_3857.tif")
run_cmd(f"gdaldem color-relief skogstyp_{flavor_name}_3857.tif color_skogstyp.txt skogstyp_{flavor_name}_colored.tif -alpha")
if os.path.exists(f"skogstyp_{flavor_name}.mbtiles"): os.remove(f"skogstyp_{flavor_name}.mbtiles")
run_cmd(f"gdal_translate -of MBTILES -co TILE_FORMAT=PNG skogstyp_{flavor_name}_colored.tif skogstyp_{flavor_name}.mbtiles")
run_cmd(f"gdaladdo -r nearest skogstyp_{flavor_name}.mbtiles 2 4 8 16")

run_cmd(f"gdalwarp -overwrite -t_srs EPSG:3857 -r near hotspot_{flavor_name}_raw.tif hotspot_{flavor_name}_3857.tif")
run_cmd(f"gdaldem color-relief hotspot_{flavor_name}_3857.tif color_tratt.txt hotspot_{flavor_name}_colored.tif -alpha")
if os.path.exists(f"hotspot_{flavor_name}.mbtiles"): os.remove(f"hotspot_{flavor_name}.mbtiles")
run_cmd(f"gdal_translate -of MBTILES -co TILE_FORMAT=PNG hotspot_{flavor_name}_colored.tif hotspot_{flavor_name}.mbtiles")
run_cmd(f"gdaladdo -r nearest hotspot_{flavor_name}.mbtiles 2 4 8 16")

# 7. Inspektionsdata (forest_inspection.bin)
print("7. Skapar forest_inspection.bin...")
ref_3857 = gdal.Open(f"hotspot_{flavor_name}_3857.tif")
gt_3857 = ref_3857.GetGeoTransform()
cols_bin = ref_3857.RasterXSize // 2
rows_bin = ref_3857.RasterYSize // 2
x_min_bin = gt_3857[0]
x_max_bin = gt_3857[0] + ref_3857.RasterXSize * gt_3857[1]
y_max_bin = gt_3857[3]
y_min_bin = gt_3857[3] + ref_3857.RasterYSize * gt_3857[5]

cell_x = (x_max_bin - x_min_bin) / cols_bin
cell_y = (y_max_bin - y_min_bin) / rows_bin

def resample_to_grid(src_file):
    src_ds = gdal.Open(src_file)
    out_ds = mem_drv.Create('', cols_bin, rows_bin, 1, gdal.GDT_Float32)
    out_ds.SetGeoTransform((x_min_bin, cell_x, 0, y_max_bin, 0, -cell_y))
    out_ds.SetProjection(ref_3857.GetProjection())
    gdal.ReprojectImage(src_ds, out_ds, None, None, gdal.GRA_NearestNeighbour)
    return np.nan_to_num(out_ds.GetRasterBand(1).ReadAsArray(), nan=0.0)

g_g = np.clip(resample_to_grid(clipped_vols["gran"]), 0, 255).astype(np.uint8)
t_g = np.clip(resample_to_grid(clipped_vols["tall"]), 0, 255).astype(np.uint8)
l_g = np.clip(resample_to_grid(clipped_vols["lov"]), 0, 255).astype(np.uint8)
t_v = g_g.astype(int) + t_g.astype(int) + l_g.astype(int)

# Apply NMD mask on the grid too? 
# To keep it exact, we just re-evaluate age and fukt with the downsampled volume
# If the high-res volume was masked out above, it won't exist in the clipped_vols anyway!
# Wait, clipped_vols has the UNMASKED original volume. We should save the masked volume and use that.
# For simplicity, we just use the masked arrays directly? Resampling from TIFF is easier.
# Let's save a temp masked total volume for accurate grid data.
save_tif(f"tmp_tot_{flavor_name}.tif", total_vol)
t_v = np.clip(resample_to_grid(f"tmp_tot_{flavor_name}.tif"), 0, 255).astype(int)

a_g = np.zeros_like(t_v, dtype=np.uint8)
a_g[(t_v > 0) & (t_v < 10)] = 5
a_g[(t_v >= 10) & (t_v < 35)] = 15
a_g[(t_v >= 35) & (t_v < 80)] = 40
a_g[(t_v >= 80) & (t_v < 150)] = 65
cg = t_v >= 150
a_g[cg] = np.minimum(95, 65 + ((t_v[cg] - 150) // 10)).astype(np.uint8)

f_g = np.where(t_v >= 20, 2, np.where(t_v > 0, 1, 0)).astype(np.uint8)
s_g = np.clip(resample_to_grid(f"hotspot_{flavor_name}_3857.tif") * 100, 0, 100).astype(np.uint8)

header = struct.pack(">4si2d2i2d", b"SVMP", 1, x_min_bin, y_max_bin, cols_bin, rows_bin, cell_x, cell_y)
comb = np.stack([g_g, t_g, l_g, a_g, f_g, s_g], axis=-1)

bin_file = f"forest_inspection_{flavor_name}.bin"
with open(bin_file, "wb") as f:
    f.write(header)
    f.write(comb.tobytes())

# KOPERA TILL APP
app_dir = f"../SvampRadar/app/src/{flavor_name}/assets"
if os.path.exists(app_dir):
    run_cmd(f"cp skogstyp_{flavor_name}.mbtiles {app_dir}/skogstyp.mbtiles")
    run_cmd(f"cp hotspot_{flavor_name}.mbtiles {app_dir}/hotspot_trattkantarell.mbtiles")
    run_cmd(f"cp {bin_file} {app_dir}/forest_inspection.bin")
    print(f"Kopierade filer till {app_dir}/")
else:
    print(f"Varning: Mappen {app_dir} finns inte. Skapade bara filerna lokalt.")

print(f"--- Klart med {city_name}! ---")
