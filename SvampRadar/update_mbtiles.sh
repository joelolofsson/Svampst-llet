#!/bin/bash
cat << 'KOTLIN' > /home/joel/projectArea/hittaSkogClone/SvampRadar/app/src/main/java/se/svampradar/app/MBTilesTileSource.kt
package se.svampradar.app

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.util.Log
import org.maplibre.android.style.sources.RasterSource
import org.maplibre.android.style.sources.TileSet
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.Executors
import kotlin.math.pow

class MBTilesTileSource(private val context: Context, private val port: Int = 8080) {
    private var serverSocket: ServerSocket? = null
    private val threadPool = Executors.newFixedThreadPool(4)
    private var isRunning = false
    
    private val dbs = mutableMapOf<String, SQLiteDatabase>()

    fun start() {
        if (isRunning) return
        isRunning = true
        Thread {
            try {
                serverSocket = ServerSocket(port)
                while (isRunning) {
                    val client = serverSocket?.accept() ?: break
                    threadPool.submit { handleClient(client) }
                }
            } catch (e: Exception) {
                Log.e("MBTilesTileSource", "Server error", e)
            }
        }.start()
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
                            val header = "HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nContent-Length: ${tileData.size}\r\n\r\n"
                            out.write(header.toByteArray())
                            out.write(tileData)
                        } else {
                            val header = "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n"
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
        // Check if database exists for this layer
        val dbPath = when (layer) {
            "trattkantarell" -> File(context.filesDir, "hotspot_trattkantarell.mbtiles")
            "gulkantarell" -> File(context.filesDir, "hotspot_gulkantarell.mbtiles")
            "basemap" -> File(context.filesDir, "opentopomap_ale_lilla_edet.mbtiles")
            else -> return null
        }
        
        if (dbPath.exists()) {
            val db = dbs.getOrPut(layer) {
                SQLiteDatabase.openDatabase(dbPath.absolutePath, null, SQLiteDatabase.OPEN_READONLY)
            }
            val tileData = getTileFromDb(db, z, x, y)
            if (tileData != null) return tileData
        }

        // If not found and it's a hotspot, return placeholder as fallback? 
        // Wait, instructions say: "If not, show a message suggesting to download/copy the data"
        // Let's just return null if file doesn't exist, and the UI will show the message if files are missing.
        
        return null
    }

    fun createRasterSource(sourceId: String, layerName: String): RasterSource {
        val tileSet = TileSet("2.2.0", "http://localhost:$port/$layerName/{z}/{x}/{y}.png")
        return RasterSource(sourceId, tileSet, 256)
    }
}
KOTLIN
