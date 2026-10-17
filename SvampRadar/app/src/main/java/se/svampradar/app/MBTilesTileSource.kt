package se.svampradar.app

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.util.Log
import org.maplibre.android.style.sources.RasterSource
import org.maplibre.android.style.sources.TileSet
import java.io.ByteArrayOutputStream
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
        ensureAssetsExtracted()
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
            try {
                it.close()
            } catch (e: Exception) {
            }
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
                            val header = "HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nContent-Length: ${tileData.size}\r\nConnection: close\r\nAccess-Control-Allow-Origin: *\r\n\r\n"
                            out.write(header.toByteArray())
                            out.write(tileData)
                        } else {
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
            try {
                client.close()
            } catch (e: Exception) {
            }
        }
    }

    private fun getTileFromDb(db: SQLiteDatabase, z: Int, x: Int, y: Int): ByteArray? {
        val yTms = (1 shl z) - 1 - y
        try {
            db.rawQuery(
                "SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
                arrayOf(z.toString(), x.toString(), yTms.toString())
            ).use { cursor ->
                if (cursor.moveToFirst()) {
                    return cursor.getBlob(0)
                }
            }
        } catch (e: Exception) {
            Log.e("MBTilesTileSource", "Error reading tile", e)
        }
        return null
    }

    @Synchronized
    private fun ensureAssetsExtracted() {
        try {
            val assetList = (context.assets.list("") ?: emptyArray()).filter { it.endsWith(".mbtiles") }.toSet()
            val versionFile = File(context.filesDir, ".mbtiles_asset_version")
            val currentVersionTag = "${BuildConfig.VERSION_CODE}_${BuildConfig.VERSION_NAME}_${BuildConfig.FLAVOR}"
            val savedVersionTag = if (versionFile.exists()) versionFile.readText().trim() else ""
            val forceOverwrite = savedVersionTag != currentVersionTag

            // Rensa bort gamla .mbtiles i filesDir som inte längre finns i APK:ns assets
            context.filesDir.listFiles()?.forEach { existing ->
                if (existing.name.endsWith(".mbtiles") && existing.name !in assetList) {
                    existing.delete()
                    Log.i("MBTilesTileSource", "Removed obsolete MBTiles file: ${existing.name}")
                }
            }

            for (name in assetList) {
                val f = File(context.filesDir, name)
                if (forceOverwrite || !f.exists() || f.length() == 0L) {
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

            if (forceOverwrite) {
                versionFile.writeText(currentVersionTag)
            }
        } catch (e: Exception) {
            Log.e("MBTilesTileSource", "Failed to extract assets", e)
        }
    }

    @Synchronized
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
            context.filesDir.listFiles()?.sortedBy { it.name }?.forEach { file ->
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
        if (databases.isEmpty()) return null

        val matchingTiles = mutableListOf<ByteArray>()
        for (db in databases) {
            val tileData = getTileFromDb(db, z, x, y)
            if (tileData != null) {
                matchingTiles.add(tileData)
            }
        }

        if (matchingTiles.isEmpty()) return null
        if (matchingTiles.size == 1) return matchingTiles[0]

        // Om flera kommuners MBTiles överlappar på samma tile (vid kommungräns), slå ihop dem med alfa-kanal
        return try {
            val combined = Bitmap.createBitmap(256, 256, Bitmap.Config.ARGB_8888)
            val canvas = Canvas(combined)
            for (bytes in matchingTiles) {
                val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: continue
                canvas.drawBitmap(bmp, 0f, 0f, null)
                bmp.recycle()
            }
            val out = ByteArrayOutputStream()
            combined.compress(Bitmap.CompressFormat.PNG, 100, out)
            combined.recycle()
            out.toByteArray()
        } catch (e: Exception) {
            matchingTiles[0]
        }
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
