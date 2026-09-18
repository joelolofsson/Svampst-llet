package se.svampradar.app

import android.content.Context
import android.util.Log
import java.io.File
import java.io.FileOutputStream
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.*

data class ForestInspection(
    val granVol: Int,
    val tallVol: Int,
    val lovVol: Int,
    val totalVol: Int,
    val age: Int,
    val moistureClass: Int, // 1=Torr-frisk, 2=Frisk-fuktig, 3=Fuktig-blöt, 4=Vatten
    val score: Int, // 0-100
    val motivation: String,
    val dominantSpecies: String
)

private class GridFile(
    val raf: RandomAccessFile,
    val xMin: Double,
    val yMax: Double,
    val cols: Int,
    val rows: Int,
    val cellX: Double,
    val cellY: Double
) {
    val xMax: Double = xMin + cols * cellX
    val yMin: Double = yMax - rows * cellY

    fun contains(xMerc: Double, yMerc: Double): Boolean {
        return xMerc in xMin..xMax && yMerc in yMin..yMax
    }

    fun readCell(r: Int, c: Int): ByteArray? {
        if (r !in 0 until rows || c !in 0 until cols) return null
        val off = 48L + (r.toLong() * cols + c) * 6L
        raf.seek(off)
        val d = ByteArray(6)
        raf.readFully(d)
        return d
    }
}

class ForestDataInspector(private val context: Context) {
    private val grids = mutableListOf<GridFile>()

    init {
        extractAndLoadGrids()
    }

    private fun extractAndLoadGrids() {
        try {
            val assetList = context.assets.list("") ?: return
            for (name in assetList) {
                if (name.startsWith("forest_inspection") && name.endsWith(".bin")) {
                    val f = File(context.filesDir, name)
                    if (!f.exists() || f.length() == 0L) {
                        try {
                            context.assets.open(name).use { input ->
                                FileOutputStream(f).use { output ->
                                    input.copyTo(output)
                                }
                            }
                            Log.i("ForestDataInspector", "Extracted $name from assets (${f.length()} bytes)")
                        } catch (e: Exception) {
                            Log.e("ForestDataInspector", "Failed to extract asset $name", e)
                        }
                    }
                }
            }
        } catch (e: Exception) {
            Log.e("ForestDataInspector", "Failed to list assets", e)
        }

        context.filesDir.listFiles()?.forEach { file ->
            if (file.name.startsWith("forest_inspection") && file.name.endsWith(".bin") && file.length() > 48) {
                try {
                    val raf = RandomAccessFile(file, "r")
                    val headerBytes = ByteArray(48)
                    raf.readFully(headerBytes)
                    val buffer = ByteBuffer.wrap(headerBytes).order(ByteOrder.BIG_ENDIAN)

                    val magic = ByteArray(4)
                    buffer.get(magic)
                    val magicStr = String(magic)
                    val version = buffer.int

                    if (magicStr == "SVMP" && version == 1) {
                        val xMin = buffer.double
                        val yMax = buffer.double
                        val cols = buffer.int
                        val rows = buffer.int
                        val cellX = buffer.double
                        val cellY = buffer.double
                        grids.add(GridFile(raf, xMin, yMax, cols, rows, cellX, cellY))
                        Log.i("ForestDataInspector", "Loaded inspection grid ${file.name}: ${cols}x${rows}, cell: ${cellX}x${cellY}")
                    } else {
                        raf.close()
                    }
                } catch (e: Exception) {
                    Log.e("ForestDataInspector", "Failed to load grid from ${file.name}", e)
                }
            }
        }
    }

    fun inspect(lat: Double, lon: Double): ForestInspection? {
        if (grids.isEmpty()) return null

        try {
            // Konvertera WGS84 (lat, lon) till Web Mercator (EPSG:3857)
            val xMerc = lon * 20037508.34 / 180.0
            var yMerc = ln(tan((90.0 + lat) * Math.PI / 360.0)) / (Math.PI / 180.0)
            yMerc = yMerc * 20037508.34 / 180.0

            val grid = grids.firstOrNull { it.contains(xMerc, yMerc) } ?: return null

            val col = ((xMerc - grid.xMin) / grid.cellX).toInt()
            val row = ((grid.yMax - yMerc) / grid.cellY).toInt()

            if (col < 0 || col >= grid.cols || row < 0 || row >= grid.rows) {
                return null
            }

            synchronized(this) {
                var data = grid.readCell(row, col) ?: return null
                var gran = data[0].toInt() and 0xFF
                var tall = data[1].toInt() and 0xFF
                var lov = data[2].toInt() and 0xFF
                var age = data[3].toInt() and 0xFF
                var fukt = data[4].toInt() and 0xFF
                var score = data[5].toInt() and 0xFF
                var total = gran + tall + lov

                // Om man klickar i en liten glänta/stig (total == 0), sök i 3x3-grannskapet
                if (total == 0) {
                    var bestMetric = -1
                    var bestData = data
                    for (dr in -1..1) {
                        for (dc in -1..1) {
                            val neighbor = grid.readCell(row + dr, col + dc) ?: continue
                            val nTotal = (neighbor[0].toInt() and 0xFF) + (neighbor[1].toInt() and 0xFF) + (neighbor[2].toInt() and 0xFF)
                            val nScore = neighbor[5].toInt() and 0xFF
                            val metric = nScore * 1000 + nTotal
                            if (metric > bestMetric && nTotal > 0) {
                                bestMetric = metric
                                bestData = neighbor
                            }
                        }
                    }
                    if (bestMetric > 0) {
                        data = bestData
                        gran = data[0].toInt() and 0xFF
                        tall = data[1].toInt() and 0xFF
                        lov = data[2].toInt() and 0xFF
                        age = data[3].toInt() and 0xFF
                        fukt = data[4].toInt() and 0xFF
                        score = data[5].toInt() and 0xFF
                        total = gran + tall + lov
                    }
                }

                val dominant = when {
                    total < 20 -> if (age in 1..25) "Kalhygge / Ungskog" else "Öppen mark / Bebyggelse"
                    gran >= tall && gran >= lov && gran.toDouble() / total >= 0.45 -> "Grandominerad skog"
                    tall >= gran && tall >= lov && tall.toDouble() / total >= 0.45 -> "Talldominerad skog"
                    lov >= gran && lov >= tall && lov.toDouble() / total >= 0.45 -> "Lövdominerad skog"
                    else -> "Blandskog"
                }

                val fuktStr = when (fukt) {
                    1 -> "Torr–frisk mark (Klass 1)"
                    2 -> "Frisk–fuktig mark (Klass 2, Optimal)"
                    3 -> "Fuktig–blöt mark (Klass 3)"
                    4 -> "Vatten / Sankmark (Klass 4)"
                    else -> "Okänd fuktighet"
                }

                val motivering = buildString {
                    if (score >= 70) {
                        append("Hög potential. ")
                    } else if (score >= 40) {
                        append("Goda förutsättningar. ")
                    } else if (total < 20) {
                        append("Ingen etablerad skog här. ")
                    } else if (age < 35) {
                        append("För ung skog ($age år). ")
                    } else if (fukt == 1) {
                        append("Marken är för torr (Klass 1). ")
                    } else {
                        append("Måttlig potential. ")
                    }

                    if (total >= 20) {
                        append("Ålder: $age år. Trädvolym: $total m³/ha. ")
                        if (gran > 50) append("Gott om gran ($gran m³/ha). ")
                        if (fukt == 2) append("Optimal markfuktighet för trattkantarell.")
                    }
                }

                return ForestInspection(
                    granVol = gran,
                    tallVol = tall,
                    lovVol = lov,
                    totalVol = total,
                    age = age,
                    moistureClass = fukt,
                    score = score,
                    motivation = motivering,
                    dominantSpecies = dominant
                )
            }
        } catch (e: Exception) {
            Log.e("ForestDataInspector", "Error during location inspection", e)
            return null
        }
    }

    fun close() {
        grids.forEach {
            try { it.raf.close() } catch (e: Exception) {}
        }
        grids.clear()
    }
}
