import sqlite3
import os
from http.server import SimpleHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

PORT = 8000
# Vi pekar servern direkt till de genererade filerna för Göteborg (som vi nyss skapade)
MBTILES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../SvampRadar/app/src/goteborg/assets/"))

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
                # Därför måste vi vända (flippa) Y-axeln:
                tms_y = (1 << z) - 1 - y

                mbtiles_path = os.path.join(MBTILES_DIR, f"{layer_name}.mbtiles")
                if not os.path.exists(mbtiles_path):
                    self.send_error(404, f"Layer {layer_name} not found")
                    return

                try:
                    conn = sqlite3.connect(mbtiles_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?", (z, x, tms_y))
                    row = cursor.fetchone()
                    conn.close()

                    if row:
                        self.send_response(200)
                        self.send_header("Content-type", "image/png")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        self.wfile.write(row[0])
                    else:
                        # Om tile saknas (vattnet/staden), skicka 404 (transparent/ingenting)
                        self.send_response(404)
                        self.end_headers()
                except Exception as e:
                    self.send_error(500, str(e))
            else:
                self.send_error(400, "Invalid tile URL")
        
        # Annars, servera bara index.html som vanligt
        else:
            super().do_GET()

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    pass

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = ThreadingHTTPServer(('0.0.0.0', PORT), TileServerHandler)
    print(f"==================================================")
    print(f"🚀 SvampRadar Web Server körs på: http://localhost:{PORT}")
    print(f"Mapp för kartdata: {MBTILES_DIR}")
    print(f"==================================================")
    server.serve_forever()
