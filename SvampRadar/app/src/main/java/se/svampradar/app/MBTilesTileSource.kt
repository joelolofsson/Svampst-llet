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
    
    private val dbs = mutableMapOf<String, MutableList<SQLiteDatabase>>()

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
        dbs.values.flatten().forEach {
            try { it.close() } catch (e: Exception) {}
        }
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

    private var assetsExtracted = false

    private fun ensureAssetsExtracted() {
        if (assetsExtracted) return
        assetsExtracted = true
        try {
            val list = context.assets.list("") ?: return
            for (name in list) {
                if (name.endsWith(".mbtiles")) {
                    val f = File(context.filesDir, name)
                    if (!f.exists() || f.length() == 0L) {
                        try {
                            context.assets.open(name).use { input ->
                                FileOutputStream(f).use { output ->
                                    input.copyTo(output)
                                }
                            }
                            Log.i("MBTilesTileSource", "Extracted $name from assets (${f.length()} bytes)")
                        } catch (e: Exception) {
                            Log.e("MBTilesTileSource", "Failed to extract asset $name", e)
                        }
                    }
                }
            }
        } catch (e: Exception) {
            Log.e("MBTilesTileSource", "Failed to list assets", e)
        }
    }

    private fun getDbsForLayer(layer: String): List<SQLiteDatabase> {
        return dbs.getOrPut(layer) {
            ensureAssetsExtracted()
            val pattern = when (layer) {
                "trattkantarell" -> Regex(".*trattkantarell.*\\.mbtiles$")
                "gulkantarell" -> Regex(".*gulkantarell.*\\.mbtiles$")
                "markfuktighet" -> Regex(".*markfuktighet.*\\.mbtiles$")
                "skogstyp" -> Regex(".*skogstyp.*\\.mbtiles$")
                "basemap" -> Regex(".*opentopomap.*\\.mbtiles$")
                else -> return@getOrPut mutableListOf()
            }
            val list = mutableListOf<SQLiteDatabase>()
            context.filesDir.listFiles()?.forEach { file ->
                if (pattern.matches(file.name) && file.length() > 0) {
                    try {
                        val db = SQLiteDatabase.openDatabase(file.absolutePath, null, SQLiteDatabase.OPEN_READONLY)
                        Log.i("MBTilesTileSource", "Opened MBTiles for $layer: ${file.name} (${file.length()} bytes)")
                        list.add(db)
                    } catch (e: Exception) {
                        Log.e("MBTilesTileSource", "Failed to open ${file.name}", e)
                    }
                }
            }
            list
        }
    }

    private fun getTile(layer: String, z: Int, x: Int, y: Int): ByteArray? {
        val databases = getDbsForLayer(layer)
        for (db in databases) {
            val tileData = getTileFromDb(db, z, x, y)
            if (tileData != null) return tileData
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
