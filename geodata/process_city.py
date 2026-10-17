#!/usr/bin/env python3
"""
Enhetlig, deterministisk geodata-pipeline för SvampRadar (inga kommunspecifika undantag).

Datakällor (samtliga nationella och officiella):
1. SCB / Lantmäteriet: kommuner.geojson (kommungränser)
2. Naturvårdsverket: NMD2023bas_v2_1.tif (Nationella Marktäckedata 2023, 10m)
3. SLU Skogskarta: GranVol_leaf.tif, TallVol_leaf.tif, LovVol_leaf.tif (Trädvolym m³sk/ha, 12.5m)
4. SLU DTW: SLUMarkfuktighetKlassad.tif (Markfuktighet klass 1-4, 2m -> 12.5m)
5. SLU / Skogsstyrelsen SGD2: Beståndsmedelsålder 2025 (gran, tall, björk, blandskog, 10m -> 12.5m)

Användning:
  python process_city.py <KommunNamn> <FlavorName>
  python process_city.py --all
"""

import os
import sys
import shutil
import struct
import subprocess
import numpy as np
from osgeo import gdal

gdal.UseExceptions()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

GEOJSON_SRC = "kommuner.geojson"
NMD_SRC = "NMD2023_basskikt_v2_1/NMD2023bas_v2_1.tif"
DTW_SRC = "SLUMarkfuktighetKlassad.tif"
VOL_SOURCES = {
    "gran": "GranVol_leaf.tif",
    "tall": "TallVol_leaf.tif",
    "lov": "LovVol_leaf.tif",
}
SLU_AGE_BASE_URL = "/vsicurl/https://gis.slu.se/data/slu_skogliga_grunddata/SGD2/data/alder/data"
AGE_KINDS = ["gran", "tall", "bjork", "blandskog"]

ALL_CITIES = [
    ("Ale,Lilla Edet", "aleLillaEdet"),
    ("Göteborg", "goteborg"),
    ("Lidköping", "lidkoping"),
    ("Mark", "mark"),
]


def run_cmd(cmd):
    print(f"  -> Kör: {cmd}")
    res = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.stderr:
        for line in res.stderr.strip().splitlines():
            if "Warning" not in line and "Copying raster attribute table" not in line:
                print(f"     {line}")


def save_tif(filename, array, cols, rows, gt, proj, dtype=gdal.GDT_Byte, no_data=0):
    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(filename, cols, rows, 1, dtype, options=["COMPRESS=LZW"])
    ds.SetGeoTransform(gt)
    ds.SetProjection(proj)
    band = ds.GetRasterBand(1)
    band.WriteArray(array)
    if no_data is not None:
        band.SetNoDataValue(no_data)
    ds.FlushCache()
    ds = None


def create_mem_ds(array, cols, rows, gt, proj, dtype=gdal.GDT_Float32):
    drv = gdal.GetDriverByName("MEM")
    ds = drv.Create("", cols, rows, 1, dtype)
    ds.SetGeoTransform(gt)
    ds.SetProjection(proj)
    ds.GetRasterBand(1).WriteArray(array)
    return ds


def matches_grid(filepath, cols, rows):
    if not os.path.exists(filepath):
        return False
    try:
        ds = gdal.Open(filepath)
        return ds.RasterXSize == cols and ds.RasterYSize == rows
    except Exception:
        return False


def process_city(city_name, flavor_name):
    print(f"\n==================================================================")
    print(f"Startar geodata-pipeline för {city_name} (flavor: {flavor_name})")
    print(f"==================================================================")

    for req in [GEOJSON_SRC, NMD_SRC, DTW_SRC] + list(VOL_SOURCES.values()):
        if not os.path.exists(req):
            raise FileNotFoundError(f"Saknar obligatorisk källfil: {req}")

    # 1. Extrahera kommunpolygon i WGS84 och SWEREF 99 TM (EPSG:3006)
    print("1. Extraherar kommungränser (WGS84 & SWEREF 99 TM)...")
    city_wgs84 = f"{flavor_name}_wgs84.geojson"
    city_sweref = f"{flavor_name}_sweref.geojson"

    cities = [c.strip() for c in city_name.split(",")]
    where_clause = " OR ".join([f"kom_namn = '{c}'" for c in cities])

    if os.path.exists(city_wgs84):
        os.remove(city_wgs84)
    run_cmd(f'ogr2ogr -f GeoJSON -where "{where_clause}" {city_wgs84} {GEOJSON_SRC}')

    if os.path.exists(city_sweref):
        os.remove(city_sweref)
    run_cmd(f"ogr2ogr -f GeoJSON -t_srs EPSG:3006 {city_sweref} {city_wgs84}")

    # 2. Klipp trädvolymraster med -dstnodata 65535 (bevarar äkta 0-volymer!)
    print("2. Klipper SLU trädvolymraster (Gran, Tall, Löv) med NoData=65535...")
    clipped_vols = {}
    for name, src_file in VOL_SOURCES.items():
        out_file = f"{name}Vol_{flavor_name}.tif"
        if not os.path.exists(out_file):
            run_cmd(
                f"gdalwarp -overwrite -cutline {city_sweref} -crop_to_cutline "
                f"-dstnodata 65535 {src_file} {out_file}"
            )
        clipped_vols[name] = out_file

    gran_ds = gdal.Open(clipped_vols["gran"])
    gt = gran_ds.GetGeoTransform()
    proj = gran_ds.GetProjection()
    cols = gran_ds.RasterXSize
    rows = gran_ds.RasterYSize
    xmin = gt[0]
    ymax = gt[3]
    xmax = xmin + cols * gt[1]
    ymin = ymax + rows * gt[5]

    print(f"   Referensgrid (EPSG:3006): {cols}x{rows} pixlar, upplösning {gt[1]}m")

    # 3a. Klipp NMD2023 till exakt samma grid
    print("3a. Klipper NMD2023 markanvändning till exakt kommun-grid...")
    nmd_city = f"nmd_{flavor_name}.tif"
    if not matches_grid(nmd_city, cols, rows):
        run_cmd(f"gdalwarp -overwrite -te {xmin} {ymin} {xmax} {ymax} -ts {cols} {rows} -r near {NMD_SRC} {nmd_city}")

    # 3b. Klipp SLU DTW Markfuktighet till exakt samma grid
    print("3b. Klipper SLU DTW Markfuktighetskarta till exakt kommun-grid...")
    fukt_grid_file = f"markfuktighet_{flavor_name}_grid.tif"
    if not matches_grid(fukt_grid_file, cols, rows):
        run_cmd(f"gdalwarp -overwrite -te {xmin} {ymin} {xmax} {ymax} -ts {cols} {rows} -r near {DTW_SRC} {fukt_grid_file}")

    # 3c. Klipp SLU Beståndsmedelålder 2025 (gran, tall, björk, blandskog) till exakt samma grid
    print("3c. Klipper SLU Beståndsmedelålder 2025 (gran, tall, björk, blandskog)...")
    age_files = {}
    for kind in AGE_KINDS:
        out_age = f"alder_{kind}_{flavor_name}.tif"
        if not matches_grid(out_age, cols, rows):
            remote_tif = f"{SLU_AGE_BASE_URL}/Best%c3%a5ndsmedels%c3%a5lder_{kind}.tif"
            run_cmd(f'gdalwarp -overwrite -te {xmin} {ymin} {xmax} {ymax} -ts {cols} {rows} -r near "{remote_tif}" {out_age}')
        age_files[kind] = out_age

    # 4. Läs in samtliga raster och beräkna maskade variabler
    print("4. Läser in raster och tillämpar strikt NMD2023- och kommungränsmaskning...")
    gran_raw = gran_ds.GetRasterBand(1).ReadAsArray()
    tall_ds = gdal.Open(clipped_vols["tall"])
    tall_raw = tall_ds.GetRasterBand(1).ReadAsArray()
    lov_ds = gdal.Open(clipped_vols["lov"])
    lov_raw = lov_ds.GetRasterBand(1).ReadAsArray()

    inside_mask = gran_raw != 65535

    nmd_ds = gdal.Open(nmd_city)
    nmd = nmd_ds.GetRasterBand(1).ReadAsArray()

    fukt_ds = gdal.Open(fukt_grid_file)
    fukt_raw = fukt_ds.GetRasterBand(1).ReadAsArray()

    # NMD 2023 klasser:
    # 111-118 = Skog på fastmark (118 = Temporärt ej skog / Kalhygge)
    # 121-128 = Skog på våtmark (128 = Temporärt ej skog / Kalhygge)
    # Alla övriga koder (3 åker, 51-54 bebyggelse/väg, 61-62 vatten, 200-228 öppen myr,
    # 411 hällmark, 4211-4233 öppen gräs-/buskmark) är ICKE-SKOG.
    nmd_forest = np.isin(
        nmd,
        [111, 112, 113, 114, 115, 116, 117, 118, 121, 122, 123, 124, 125, 126, 127, 128],
    ) & inside_mask
    nmd_hygge = np.isin(nmd, [118, 128]) & inside_mask
    nmd_conifer = np.isin(nmd, [111, 112, 113, 114, 121, 122, 123, 124]) & inside_mask

    gran = np.where(nmd_forest & (gran_raw >= 0) & (gran_raw != 65535), gran_raw, 0).astype(np.float32)
    tall = np.where(nmd_forest & (tall_raw >= 0) & (tall_raw != 65535), tall_raw, 0).astype(np.float32)
    lov = np.where(nmd_forest & (lov_raw >= 0) & (lov_raw != 65535), lov_raw, 0).astype(np.float32)

    # På NMD 2023 kalhyggen (118/128) nollställs eventuell gammal volym från före avverkningen
    gran[nmd_hygge] = np.minimum(gran[nmd_hygge], 10.0)
    tall[nmd_hygge] = np.minimum(tall[nmd_hygge], 10.0)
    lov[nmd_hygge] = np.minimum(lov[nmd_hygge], 10.0)

    total_vol = gran + tall + lov
    barr_vol = gran + tall

    with np.errstate(divide="ignore", invalid="ignore"):
        p_gran = np.where(total_vol > 0, gran / total_vol, 0.0)
        p_tall = np.where(total_vol > 0, tall / total_vol, 0.0)
        p_lov = np.where(total_vol > 0, lov / total_vol, 0.0)
        barr_ratio = np.where(total_vol > 0, barr_vol / total_vol, 0.0)

    # Läs in SLU 2025 Beståndsmedelålder enligt officiell produktbeskrivning (>= 65% trädslagsandel)
    age_arrays = {}
    for kind in AGE_KINDS:
        ds_a = gdal.Open(age_files[kind])
        arr_a = ds_a.GetRasterBand(1).ReadAsArray()
        age_arrays[kind] = np.where((arr_a > 0) & (arr_a <= 250), arr_a, 0).astype(np.int16)

    age_selected = age_arrays["blandskog"].copy()
    is_gran_dom = (p_gran >= 0.65) | ((total_vol == 0) & np.isin(nmd, [112, 122]))
    is_tall_dom = (p_tall >= 0.65) | ((total_vol == 0) & np.isin(nmd, [111, 121]))
    is_lov_dom = (p_lov >= 0.65) | ((total_vol == 0) & np.isin(nmd, [115, 116, 117, 125, 126, 127]))

    age_selected[is_gran_dom] = age_arrays["gran"][is_gran_dom]
    age_selected[is_tall_dom] = age_arrays["tall"][is_tall_dom]
    age_selected[is_lov_dom] = age_arrays["bjork"][is_lov_dom]

    # Fallback till max av giltiga 2025-åldrar om den valda skogstypens ålderskarta har NoData
    age_max = np.maximum.reduce([age_arrays["gran"], age_arrays["tall"], age_arrays["bjork"], age_arrays["blandskog"]])
    age_selected = np.where(age_selected > 0, age_selected, age_max)

    age = np.zeros((rows, cols), dtype=np.uint8)
    age[nmd_forest] = np.clip(age_selected[nmd_forest], 0, 200).astype(np.uint8)
    # Kalhyggen i NMD 2023 har högst ålder 5-24 år
    age[nmd_hygge] = np.where((age[nmd_hygge] > 0) & (age[nmd_hygge] < 25), age[nmd_hygge], 5)

    # Markfuktighet (1=Torr-frisk, 2=Frisk-fuktig, 3=Fuktig-blöt, 4=Vatten/sankmark, 0=Utanför/Sjö/Hav)
    is_open_water = np.isin(nmd, [61, 62])
    fukt = np.where(inside_mask & (~is_open_water) & (fukt_raw >= 1) & (fukt_raw <= 4), fukt_raw, 0).astype(np.uint8)
    fukt_city_file = f"markfuktighet_{flavor_name}.tif"
    save_tif(fukt_city_file, fukt, cols, rows, gt, proj, gdal.GDT_Byte, no_data=0)

    # Skogstypsklassificering:
    # 0 = Ingen skog (transparent)
    # 1 = Kalhygge / Ungskog (< 25 år eller NMD 118/128) -> Blå
    # 2 = Grandominerad skog -> Mörkgrön
    # 3 = Talldominerad skog -> Orange
    # 4 = Lövdominerad skog -> Ljusgrön
    # 5 = Blandskog -> Olivgrön
    skogstyp = np.zeros((rows, cols), dtype=np.uint8)
    cond_hygge = nmd_hygge | (nmd_forest & (age > 0) & (age < 25)) | (nmd_forest & (total_vol < 35) & (age < 25))
    skogstyp[cond_hygge] = 1

    cond_skog = nmd_forest & (~cond_hygge)
    skogstyp[cond_skog & ((p_gran >= 0.45) | ((total_vol < 35) & np.isin(nmd, [112, 122])))] = 2
    skogstyp[cond_skog & (((p_tall >= 0.45) & (p_tall > p_gran)) | ((total_vol < 35) & np.isin(nmd, [111, 121])))] = 3
    skogstyp[
        cond_skog
        & (
            ((p_lov >= 0.45) & (p_lov > p_gran) & (p_lov > p_tall))
            | ((total_vol < 35) & np.isin(nmd, [115, 116, 117, 125, 126, 127]))
        )
    ] = 4
    skogstyp[cond_skog & (skogstyp == 0)] = 5

    skogstyp_raw_file = f"skogstyp_{flavor_name}_raw.tif"
    save_tif(skogstyp_raw_file, skogstyp, cols, rows, gt, proj, gdal.GDT_Byte, no_data=0)

    # 5. Sannolikhetsmodell för Trattkantarell (Strikt biologisk modell utan undantag)
    print("5. Beräknar trattkantarell-hotspots (NMD + Volym + SLU 2025 Ålder + SLU DTW Fukt)...")
    cond_vol = (total_vol >= 150) & (total_vol <= 600)
    cond_barr = (barr_vol >= 70) & (barr_ratio >= 0.50) & (gran >= 40)
    cond_alder = age >= 50
    cond_fukt = (fukt == 2) | (fukt == 3)

    valid = nmd_conifer & (~cond_hygge) & cond_vol & cond_barr & cond_alder & cond_fukt

    # Sammanhängande yta >= 20 pixlar (~0.3 ha) med 8-grannskap
    mem_drv = gdal.GetDriverByName("MEM")
    tmp_ds = mem_drv.Create("", cols, rows, 1, gdal.GDT_Byte)
    tmp_ds.GetRasterBand(1).WriteArray(valid.astype(np.uint8))
    sieve_ds = mem_drv.Create("", cols, rows, 1, gdal.GDT_Byte)
    gdal.SieveFilter(tmp_ds.GetRasterBand(1), None, sieve_ds.GetRasterBand(1), 20, 8)
    valid_filtered = (sieve_ds.GetRasterBand(1).ReadAsArray() > 0) & valid

    hotspot = np.zeros((rows, cols), dtype=np.float32)
    hotspot[valid_filtered] = 0.4
    hotspot[valid_filtered & (gran >= 100)] += 0.2
    hotspot[valid_filtered & (fukt == 2)] += 0.2
    hotspot[valid_filtered & (age >= 70)] += 0.2

    hotspot_raw_file = f"hotspot_{flavor_name}_raw.tif"
    save_tif(hotspot_raw_file, hotspot, cols, rows, gt, proj, gdal.GDT_Float32, no_data=0)

    # 6. Omprojicering till Web Mercator (EPSG:3857) och MBTiles-generering
    print("6. Reprojicerar till EPSG:3857 och bygger MBTiles...")
    layers_to_export = [
        ("skogstyp", skogstyp_raw_file, "color_skogstyp.txt"),
        ("hotspot", hotspot_raw_file, "color_tratt.txt"),
        ("markfuktighet", fukt_city_file, "color_fukt.txt"),
    ]
    for prefix, raw_tif, color_txt in layers_to_export:
        tif_3857 = f"{prefix}_{flavor_name}_3857.tif"
        tif_colored = f"{prefix}_{flavor_name}_colored.tif"
        mbtiles_out = f"{prefix}_{flavor_name}.mbtiles"

        run_cmd(f"gdalwarp -overwrite -t_srs EPSG:3857 -r near -dstnodata 0 {raw_tif} {tif_3857}")
        run_cmd(f"gdaldem color-relief {tif_3857} {color_txt} {tif_colored} -alpha")
        if os.path.exists(mbtiles_out):
            os.remove(mbtiles_out)
        run_cmd(f"gdal_translate -of MBTILES -co TILE_FORMAT=PNG {tif_colored} {mbtiles_out}")
        run_cmd(f"gdaladdo -r nearest {mbtiles_out} 2 4 8 16")

    # 7. Skapa kompakt inspektionsgrid (forest_inspection.bin) från de MASKADE arrayerna
    print("7. Bygger forest_inspection.bin från maskade skogsdata...")
    ref_3857 = gdal.Open(f"hotspot_{flavor_name}_3857.tif")
    gt_3857 = ref_3857.GetGeoTransform()
    proj_3857 = ref_3857.GetProjection()
    cols_bin = ref_3857.RasterXSize // 2
    rows_bin = ref_3857.RasterYSize // 2
    x_min_bin = gt_3857[0]
    x_max_bin = gt_3857[0] + ref_3857.RasterXSize * gt_3857[1]
    y_max_bin = gt_3857[3]
    y_min_bin = gt_3857[3] + ref_3857.RasterYSize * gt_3857[5]

    cell_x = (x_max_bin - x_min_bin) / cols_bin
    cell_y = (y_max_bin - y_min_bin) / rows_bin

    def resample_array_to_bin_grid(arr_3006):
        src_ds = create_mem_ds(arr_3006.astype(np.float32), cols, rows, gt, proj, gdal.GDT_Float32)
        out_ds = mem_drv.Create("", cols_bin, rows_bin, 1, gdal.GDT_Float32)
        out_ds.SetGeoTransform((x_min_bin, cell_x, 0.0, y_max_bin, 0.0, -cell_y))
        out_ds.SetProjection(proj_3857)
        gdal.ReprojectImage(src_ds, out_ds, proj, proj_3857, gdal.GRA_NearestNeighbour)
        return np.nan_to_num(out_ds.GetRasterBand(1).ReadAsArray(), nan=0.0)

    g_g = np.clip(np.rint(resample_array_to_bin_grid(gran)), 0, 255).astype(np.uint8)
    t_g = np.clip(np.rint(resample_array_to_bin_grid(tall)), 0, 255).astype(np.uint8)
    l_g = np.clip(np.rint(resample_array_to_bin_grid(lov)), 0, 255).astype(np.uint8)
    a_g = np.clip(np.rint(resample_array_to_bin_grid(age)), 0, 255).astype(np.uint8)
    f_g = np.clip(np.rint(resample_array_to_bin_grid(fukt)), 0, 4).astype(np.uint8)
    s_g = np.clip(np.rint(resample_array_to_bin_grid(hotspot * 100.0)), 0, 100).astype(np.uint8)

    # Säkerställ fullständig konsistens i det nedskalade rutnätet
    outside_or_water = f_g == 0
    g_g[outside_or_water] = 0
    t_g[outside_or_water] = 0
    l_g[outside_or_water] = 0
    a_g[outside_or_water] = 0
    s_g[outside_or_water] = 0

    tot_g = g_g.astype(np.int32) + t_g.astype(np.int32) + l_g.astype(np.int32)
    s_g[tot_g < 150] = 0

    header = struct.pack(">4si2d2i2d", b"SVMP", 1, x_min_bin, y_max_bin, cols_bin, rows_bin, cell_x, cell_y)
    comb = np.stack([g_g, t_g, l_g, a_g, f_g, s_g], axis=-1)

    bin_file = f"forest_inspection_{flavor_name}.bin"
    with open(bin_file, "wb") as f:
        f.write(header)
        f.write(comb.tobytes())

    # 8. Kopiera till BÅDE kommunens flavor-mapp och full-mappen
    print("8. Synkroniserar genererade filer till Android-appens assets...")
    flavor_dir = os.path.abspath(f"../SvampRadar/app/src/{flavor_name}/assets")
    if os.path.exists(flavor_dir):
        shutil.copyfile(f"skogstyp_{flavor_name}.mbtiles", os.path.join(flavor_dir, "skogstyp.mbtiles"))
        shutil.copyfile(f"hotspot_{flavor_name}.mbtiles", os.path.join(flavor_dir, "hotspot_trattkantarell.mbtiles"))
        shutil.copyfile(f"markfuktighet_{flavor_name}.mbtiles", os.path.join(flavor_dir, "markfuktighet.mbtiles"))
        shutil.copyfile(bin_file, os.path.join(flavor_dir, "forest_inspection.bin"))
        print(f"   Uppdaterade {flavor_dir}/")

    full_dir = os.path.abspath("../SvampRadar/app/src/full/assets")
    if os.path.exists(full_dir):
        full_suffix = "ale_lilla_edet" if flavor_name == "aleLillaEdet" else flavor_name
        shutil.copyfile(f"skogstyp_{flavor_name}.mbtiles", os.path.join(full_dir, f"skogstyp_{full_suffix}.mbtiles"))
        shutil.copyfile(
            f"hotspot_{flavor_name}.mbtiles",
            os.path.join(full_dir, f"hotspot_trattkantarell_{full_suffix}.mbtiles"),
        )
        shutil.copyfile(
            f"markfuktighet_{flavor_name}.mbtiles",
            os.path.join(full_dir, f"markfuktighet_{full_suffix}.mbtiles"),
        )
        shutil.copyfile(bin_file, os.path.join(full_dir, f"forest_inspection_{full_suffix}.bin"))
        print(f"   Uppdaterade {full_dir}/*_{full_suffix}.*")

    # 9. Automatisk verifiering av invarianter
    verify_city(
        city_name=city_name,
        flavor_name=flavor_name,
        nmd_forest=nmd_forest,
        nmd_hygge=nmd_hygge,
        skogstyp=skogstyp,
        hotspot=hotspot,
        comb=comb,
    )


def verify_city(city_name, flavor_name, nmd_forest, nmd_hygge, skogstyp, hotspot, comb):
    print(f"9. Verifierar kartmodeller och dataintegritet för {city_name}...")
    non_forest = ~nmd_forest

    # Invariant 1: Ingen skog eller hotspot får ligga utanför NMD skogsmark (stad, vatten, åker, öppen mark)
    bad_skog_nonforest = int(np.count_nonzero(skogstyp[non_forest] > 0))
    bad_hotspot_nonforest = int(np.count_nonzero(hotspot[non_forest] > 0))
    assert bad_skog_nonforest == 0, f"FEL: {bad_skog_nonforest} skogspixlar utanför NMD skogsmark!"
    assert bad_hotspot_nonforest == 0, f"FEL: {bad_hotspot_nonforest} hotspotpixlar utanför NMD skogsmark!"

    # Invariant 2: NMD kalhyggen (118/128) får aldrig klassas som etablerad skog (2..5) eller hotspot
    bad_skog_hygge = int(np.count_nonzero(np.isin(skogstyp[nmd_hygge], [2, 3, 4, 5])))
    bad_hotspot_hygge = int(np.count_nonzero(hotspot[nmd_hygge] > 0))
    assert bad_skog_hygge == 0, f"FEL: {bad_skog_hygge} kalhyggespixlar klassade som mogen skog!"
    assert bad_hotspot_hygge == 0, f"FEL: {bad_hotspot_hygge} hotspotpixlar på kalhygge!"

    # Invariant 3: Inspektionsgridens poäng får aldrig vara > 0 om totalvolym < 150 eller fukt == 0
    g_b, t_b, l_b, a_b, f_b, s_b = [comb[..., i].astype(np.int32) for i in range(6)]
    tot_b = g_b + t_b + l_b
    bad_bin_score = int(np.count_nonzero((s_b > 0) & ((tot_b < 150) | (f_b == 0))))
    assert bad_bin_score == 0, f"FEL: {bad_bin_score} celler i .bin har poäng men saknar skogsvolym/fukt!"

    px_ha = (12.5 * 12.5) / 10000.0
    forest_ha = np.count_nonzero(nmd_forest) * px_ha
    hygge_ha = np.count_nonzero(skogstyp == 1) * px_ha
    gran_ha = np.count_nonzero(skogstyp == 2) * px_ha
    tall_ha = np.count_nonzero(skogstyp == 3) * px_ha
    lov_ha = np.count_nonzero(skogstyp == 4) * px_ha
    bland_ha = np.count_nonzero(skogstyp == 5) * px_ha
    hotspot_px = np.count_nonzero(hotspot > 0)
    hotspot_ha = hotspot_px * px_ha

    s40 = np.count_nonzero(np.isclose(hotspot, 0.4))
    s60 = np.count_nonzero(np.isclose(hotspot, 0.6))
    s80 = np.count_nonzero(np.isclose(hotspot, 0.8))
    s100 = np.count_nonzero(np.isclose(hotspot, 1.0))

    print(f"   [OK] Alla invarianter godkända för {city_name}!")
    print(f"   Skogsmark totalt: {forest_ha:,.0f} ha")
    print(
        f"   Skogstyper: Gran={gran_ha:,.0f} ha, Tall={tall_ha:,.0f} ha, "
        f"Löv={lov_ha:,.0f} ha, Bland={bland_ha:,.0f} ha, Hygge/Ungskog={hygge_ha:,.0f} ha"
    )
    print(
        f"   Hotspots (Trattkantarell): {hotspot_px:,} pixlar ({hotspot_ha:,.1f} ha) | "
        f"40p={s40:,}, 60p={s60:,}, 80p={s80:,}, 100p={s100:,}"
    )


def decode_png_rgba(png_bytes):
    vsi_path = "/vsimem/tmp_in.png"
    gdal.FileFromMemBuffer(vsi_path, bytes(png_bytes))
    ds = gdal.Open(vsi_path)
    arr = ds.ReadAsArray()  # (bands, 256, 256)
    ds = None
    gdal.Unlink(vsi_path)
    if arr.shape[0] == 3:
        alpha = np.full((1, arr.shape[1], arr.shape[2]), 255, dtype=np.uint8)
        arr = np.concatenate([arr, alpha], axis=0)
    return arr


def encode_png_rgba(rgba_arr):
    mem_drv = gdal.GetDriverByName("MEM")
    png_drv = gdal.GetDriverByName("PNG")
    _, h, w = rgba_arr.shape
    ds = mem_drv.Create("", w, h, 4, gdal.GDT_Byte)
    for b in range(4):
        ds.GetRasterBand(b + 1).WriteArray(rgba_arr[b])
    vsi_out = "/vsimem/tmp_out.png"
    out_ds = png_drv.CreateCopy(vsi_out, ds)
    out_ds = None
    ds = None
    f = gdal.VSIFOpenL(vsi_out, "rb")
    gdal.VSIFSeekL(f, 0, 2)
    size = gdal.VSIFTellL(f)
    gdal.VSIFSeekL(f, 0, 0)
    data = gdal.VSIFReadL(1, size, f)
    gdal.VSIFCloseL(f)
    gdal.Unlink(vsi_out)
    return bytes(data)


def stitch_overlapping_mbtiles_in_full():
    import glob
    import sqlite3

    full_dir = os.path.abspath("../SvampRadar/app/src/full/assets")
    if not os.path.exists(full_dir):
        return

    print("\n==================================================================")
    print("Sammanfogar överlappande kommungräns-tiles i full/assets/...")
    print("==================================================================")

    for prefix in ["skogstyp", "hotspot_trattkantarell", "markfuktighet"]:
        files = sorted(glob.glob(os.path.join(full_dir, f"{prefix}_*.mbtiles")))
        if len(files) < 2:
            continue

        tile_map = {}
        for fpath in files:
            conn = sqlite3.connect(fpath)
            cur = conn.cursor()
            cur.execute("SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles")
            for z, x, y, data in cur.fetchall():
                tile_map.setdefault((z, x, y), []).append((fpath, data))
            conn.close()

        overlaps = {k: v for k, v in tile_map.items() if len(v) > 1}
        stitched_count = 0
        for (z, x, y), entries in overlaps.items():
            combined = None
            for _, png_bytes in entries:
                rgba = decode_png_rgba(png_bytes)
                if combined is None:
                    combined = rgba.copy()
                else:
                    mask = rgba[3] > 0
                    for b in range(4):
                        combined[b][mask] = rgba[b][mask]
            merged_bytes = encode_png_rgba(combined)
            for fpath, _ in entries:
                conn = sqlite3.connect(fpath)
                conn.execute(
                    "UPDATE tiles SET tile_data = ? WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
                    (merged_bytes, z, x, y),
                )
                conn.commit()
                conn.close()
            stitched_count += 1
        print(f"   {prefix}: Sammanfogade {stitched_count} överlappande gräns-tiles.")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--all":
        for c_name, f_name in ALL_CITIES:
            process_city(c_name, f_name)
        stitch_overlapping_mbtiles_in_full()
    elif len(sys.argv) >= 3:
        process_city(sys.argv[1], sys.argv[2])
        stitch_overlapping_mbtiles_in_full()
    else:
        print("Användning:")
        print("  python process_city.py <KommunNamn> <FlavorName>")
        print("  python process_city.py --all")
        sys.exit(1)
