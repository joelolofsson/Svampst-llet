#!/usr/bin/env python3
"""
Download OpenTopoMap tiles and package into MBTiles SQLite database.
Bounding box: west=11.8, south=57.9, east=12.5, north=58.35
Zoom levels: 10 - 14
"""

import os
import sys
import time
import sqlite3
import random
import requests
import mercantile

WEST = 11.8
SOUTH = 57.9
EAST = 12.5
NORTH = 58.35
MIN_ZOOM = 10
MAX_ZOOM = 14

OUTPUT_MBTILES = "opentopomap_ale_lilla_edet.mbtiles"
USER_AGENT = "SvampRadar/1.0 (Educational mushroom foraging app; contact@svampradar.se)"

def init_mbtiles(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            name TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tiles (
            zoom_level INTEGER,
            tile_column INTEGER,
            tile_row INTEGER,
            tile_data BLOB,
            PRIMARY KEY (zoom_level, tile_column, tile_row)
        );
    """)
    metadata = [
        ("name", "OpenTopoMap Ale & Lilla Edet"),
        ("type", "baselayer"),
        ("version", "1.0"),
        ("description", "OpenTopoMap base map for SvampRadar"),
        ("format", "png"),
        ("bounds", f"{WEST},{SOUTH},{EAST},{NORTH}"),
        ("minzoom", str(MIN_ZOOM)),
        ("maxzoom", str(MAX_ZOOM)),
        ("center", "12.15,58.13,11")
    ]
    cur.executemany("INSERT OR REPLACE INTO metadata (name, value) VALUES (?, ?);", metadata)
    conn.commit()
    return conn

def main():
    conn = init_mbtiles(OUTPUT_MBTILES)
    cur = conn.cursor()
    
    # Get all tiles in bbox
    all_tiles = list(mercantile.tiles(WEST, SOUTH, EAST, NORTH, range(MIN_ZOOM, MAX_ZOOM + 1)))
    total_tiles = len(all_tiles)
    print(f"Total tiles to process: {total_tiles}")

    # Check already downloaded tiles
    cur.execute("SELECT zoom_level, tile_column, tile_row FROM tiles")
    existing = set(cur.fetchall())
    print(f"Existing tiles in MBTiles: {len(existing)}")

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    saved = len(existing)
    start_time = time.time()

    # Randomize order slightly to distribute load or download sequentially
    tiles_to_download = []
    for tile in all_tiles:
        tms_y = (1 << tile.z) - 1 - tile.y
        if (tile.z, tile.x, tms_y) not in existing:
            tiles_to_download.append((tile, tms_y))

    print(f"Tiles remaining to download: {len(tiles_to_download)}")

    batch = []
    batch_size = 20

    for i, (tile, tms_y) in enumerate(tiles_to_download, 1):
        url = f"https://tile.opentopomap.org/{tile.z}/{tile.x}/{tile.y}.png"
        retries = 3
        data = None

        for attempt in range(retries):
            try:
                resp = session.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.content
                    break
                elif resp.status_code == 429:
                    print(f"\nRate limited (429), sleeping 5s... (tile {tile})")
                    time.sleep(5)
                else:
                    print(f"\nTile {tile} returned HTTP {resp.status_code}")
                    time.sleep(1)
            except Exception as e:
                time.sleep(1 + attempt)

        if data:
            batch.append((tile.z, tile.x, tms_y, data))
            saved += 1
        else:
            print(f"\nFailed to download tile {tile.z}/{tile.x}/{tile.y}")

        if len(batch) >= batch_size:
            cur.executemany("INSERT OR REPLACE INTO tiles VALUES (?, ?, ?, ?)", batch)
            conn.commit()
            batch = []

        if i % 25 == 0 or i == len(tiles_to_download):
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            percent = (saved / total_tiles) * 100
            print(f"Progress: {saved}/{total_tiles} ({percent:.1f}%) | {rate:.1f} tiles/s", end="\r", flush=True)

        # Respectful delay between requests (80-120 ms)
        time.sleep(0.08 + random.uniform(0.01, 0.04))

    if batch:
        cur.executemany("INSERT OR REPLACE INTO tiles VALUES (?, ?, ?, ?)", batch)
        conn.commit()

    print(f"\nFinished! Total tiles in {OUTPUT_MBTILES}: {saved}")
    conn.close()

if __name__ == "__main__":
    main()
