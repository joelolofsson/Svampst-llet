import sqlite3
import os
import glob
from http.server import SimpleHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

PORT = 8000
# Pekar mot full/assets som innehåller samtliga kommuners geodata
ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../SvampRadar/app/src/full/assets/"))

class TileServerHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        # API för att hämta kart-tiles (t.ex. /tiles/skogstyp/10/543/321.png)
        if self.path.startswith("/tiles/"):
            parts = self.path.split("/")
            if len(parts) == 6:
                layer_name = parts[2]
                z = int(parts[3])
                x = int(parts[4])
                y_str = parts[5].split(".")[0]
                y = int(y_str)

                # MapLibre kör med XYZ (Top-Left origin), SQLite/MBTiles använder TMS (Bottom-Left origin).
                tms_y = (1 << z) - 1 - y

                # Hitta alla MBTiles-filer för detta lager (t.ex. skogstyp_goteborg.mbtiles, skogstyp_lidkoping.mbtiles, osv.)
                mbtiles_files = glob.glob(os.path.join(ASSETS_DIR, f"*{layer_name}*.mbtiles"))
                if not mbtiles_files:
                    self.send_error(404, f"Layer {layer_name} not found")
                    return

                tile_data = None
                for mb_path in mbtiles_files:
                    try:
                        conn = sqlite3.connect(mb_path)
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                            (z, x, tms_y)
                        )
                        row = cursor.fetchone()
                        conn.close()

                        if row and row[0]:
                            tile_data = row[0]
                            break
                    except Exception:
                        continue

                if tile_data:
                    self.send_response(200)
                    self.send_header("Content-type", "image/png")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Cache-Control", "public, max-age=86400")
                    self.end_headers()
                    self.wfile.write(tile_data)
                else:
                    self.send_response(404)
                    self.end_headers()
            else:
                self.send_error(400, "Invalid tile URL")
        else:
            super().do_GET()

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    pass

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = ThreadingHTTPServer(('0.0.0.0', PORT), TileServerHandler)
    print(f"==================================================")
    print(f"🚀 SvampRadar Web Server körs på: http://localhost:{PORT}")
    print(f"Mapp för kartdata (Alla städer): {ASSETS_DIR}")
    print(f"==================================================")
    server.serve_forever()
