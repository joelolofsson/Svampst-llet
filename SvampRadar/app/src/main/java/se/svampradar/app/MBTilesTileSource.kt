package se.svampradar.app

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.util.Log
import org.maplibre.android.style.sources.RasterSource
import org.maplibre.android.style.sources.TileSet
import java.io.File
import java.io.FileOutputStream
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.Executors

class MBTilesTileSource(private val context: Context, private val preferredPort: Int = 0) {
    private var serverSocket: ServerSocket? = null
    private val threadPool = Executors.newFixedThreadPool(4)
    private var isRunning = false
    var actualPort: Int = 0
        private set
    
    private val dbs = mutableMapOf<String, SQLiteDatabase>()

    fun start() {
        if (isRunning) return
        isRunning = true
        val filesDir = context.filesDir
        Log.i("MBTilesTileSource", "Files dir: ${filesDir.absolutePath}")
        filesDir.listFiles()?.forEach { f ->
            Log.i("MBTilesTileSource", "  Found file: ${f.name} (${f.length()} bytes)")
        }
        Thread {
            try {
                // Bind ONLY to 127.0.0.1 (IPv4 localhost) - not accessible from network
                serverSocket = ServerSocket(preferredPort, 50, InetAddress.getByName("127.0.0.1"))
                actualPort = serverSocket!!.localPort
                Log.i("MBTilesTileSource", "Tile server started on 127.0.0.1:$actualPort")
                while (isRunning) {
                    val client = serverSocket?.accept() ?: break
                    threadPool.submit { handleClient(client) }
                }
            } catch (e: Exception) {
                Log.e("MBTilesTileSource", "Server error", e)
            }
        }.start()
        Thread.sleep(200)
    }

    fun stop() {
        isRunning = false
        serverSocket?.close()
        threadPool.shutdown()
        dbs.values.forEach { it.close() }
        dbs.clear()
    }

    private fun handleClient(client: Socket) {
        try {
            client.getInputStream().bufferedReader().use { reader ->
                val requestLine = reader.readLine() ?: return
                if (requestLine.startsWith("GET ")) {
                    val path = requestLine.split(" ")[1]
                    val parts = path.trim('/').split("/")
                    if (parts.size >= 4) {
                        val layer = parts[0]
                        val z = parts[1].toInt()
                        val x = parts[2].toInt()
                        val yStr = parts[3].substringBefore(".png")
                        val y = yStr.toInt()

                        val tileData = getTile(layer, z, x, y)
                        val out = client.getOutputStream()
                        if (tileData != null) {
                            Log.d("MBTilesTileSource", "HIT: $layer z=$z x=$x y=$y (${tileData.size} bytes)")
                            val header = "HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nContent-Length: ${tileData.size}\r\nConnection: close\r\nAccess-Control-Allow-Origin: *\r\n\r\n"
                            out.write(header.toByteArray())
                            out.write(tileData)
                        } else {
                            Log.d("MBTilesTileSource", "MISS: $layer z=$z x=$x y=$y")
                            val header = "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
                            out.write(header.toByteArray())
                        }
                        out.flush()
                    }
                }
            }
        } catch (e: Exception) {
            // Ignore socket errors
        } finally {
            try { client.close() } catch (e: Exception) {}
        }
    }

    private fun getTileFromDb(db: SQLiteDatabase, z: Int, x: Int, y: Int): ByteArray? {
        val yTms = (1 shl z) - 1 - y
        try {
            db.rawQuery("SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?", arrayOf(z.toString(), x.toString(), yTms.toString())).use { cursor ->
                if (cursor.moveToFirst()) {
                    return cursor.getBlob(0)
                }
            }
        } catch (e: Exception) {
            Log.e("MBTilesTileSource", "Error reading tile", e)
        }
        return null
    }

    private fun getTile(layer: String, z: Int, x: Int, y: Int): ByteArray? {
        val dbFile = when (layer) {
            "trattkantarell" -> File(context.filesDir, "hotspot_trattkantarell.mbtiles")
            "gulkantarell" -> File(context.filesDir, "hotspot_gulkantarell.mbtiles")
            "markfuktighet" -> File(context.filesDir, "markfuktighet.mbtiles")
            "basemap" -> {
                val f = File(context.filesDir, "opentopomap_ale_lilla_edet.mbtiles")
                if (!f.exists()) {
                    try {
                        context.assets.open("opentopomap_ale_lilla_edet.mbtiles").use { input ->
                            FileOutputStream(f).use { output ->
                                input.copyTo(output)
                            }
                        }
                    } catch (e: Exception) {
                        Log.e("MBTilesTileSource", "Failed to copy basemap from assets", e)
                    }
                }
                f
            }
            else -> return null
        }
        
        if (dbFile.exists()) {
            val db = dbs.getOrPut(layer) {
                Log.i("MBTilesTileSource", "Opening database: ${dbFile.name} (${dbFile.length()} bytes)")
                SQLiteDatabase.openDatabase(dbFile.absolutePath, null, SQLiteDatabase.OPEN_READONLY)
            }
            val tileData = getTileFromDb(db, z, x, y)
            return tileData
        } else {
            Log.w("MBTilesTileSource", "MBTiles file not found: ${dbFile.absolutePath}")
        }

        return null
    }

    fun createRasterSource(sourceId: String, layerName: String): RasterSource {
        val url = "http://127.0.0.1:$actualPort/$layerName/{z}/{x}/{y}.png"
        Log.i("MBTilesTileSource", "Creating raster source: $sourceId -> $url")
        val tileSet = TileSet("2.2.0", url)
        tileSet.minZoom = 9f
        tileSet.maxZoom = 13f
        return RasterSource(sourceId, tileSet, 256)
    }
}
