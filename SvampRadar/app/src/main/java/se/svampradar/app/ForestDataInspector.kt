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
    val name: String,
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

    fun readCellAtMercator(xMerc: Double, yMerc: Double): ByteArray? {
        if (!contains(xMerc, yMerc)) return null
        val col = ((xMerc - xMin) / cellX).toInt()
        val row = ((yMax - yMerc) / cellY).toInt()
        if (rOutOfBounds(row, col)) return null
        val off = 48L + (row.toLong() * cols + col) * 6L
        raf.seek(off)
        val d = ByteArray(6)
        raf.readFully(d)
        return d
    }

    private fun rOutOfBounds(r: Int, c: Int): Boolean {
        return r !in 0 until rows || c !in 0 until cols
    }
}

class ForestDataInspector(private val context: Context) {
    private val grids = mutableListOf<GridFile>()

    init {
        extractAndLoadGrids()
    }

    private fun extractAndLoadGrids() {
        try {
            val assetList = (context.assets.list("") ?: emptyArray())
                .filter { it.startsWith("forest_inspection") && it.endsWith(".bin") }
                .toSet()

            val versionFile = File(context.filesDir, ".inspector_asset_version")
            val currentVersionTag = "${BuildConfig.VERSION_CODE}_${BuildConfig.VERSION_NAME}_${BuildConfig.FLAVOR}"
            val savedVersionTag = if (versionFile.exists()) versionFile.readText().trim() else ""
            val forceOverwrite = savedVersionTag != currentVersionTag

            // Rensa bort gamla .bin-filer som inte längre finns i APK:ns assets
            context.filesDir.listFiles()?.forEach { existing ->
                if (existing.name.startsWith("forest_inspection") && existing.name.endsWith(".bin") && existing.name !in assetList) {
                    existing.delete()
                    Log.i("ForestDataInspector", "Removed obsolete grid file: ${existing.name}")
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
                        Log.i("ForestDataInspector", "Extracted $name from assets (${f.length()} bytes)")
                    } catch (e: Exception) {
                        Log.e("ForestDataInspector", "Failed to extract asset $name", e)
                    }
                }
            }

            if (forceOverwrite) {
                versionFile.writeText(currentVersionTag)
            }
        } catch (e: Exception) {
            Log.e("ForestDataInspector", "Failed to extract grid assets", e)
        }

        context.filesDir.listFiles()?.sortedBy { it.name }?.forEach { file ->
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
                        grids.add(GridFile(file.name, raf, xMin, yMax, cols, rows, cellX, cellY))
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
            yMerc *= 20037508.34 / 180.0

            synchronized(this) {
                // Vid kommungränser kan flera rektangulära bounding-boxes överlappa.
                // Välj den kommunfil som faktiskt har data (innanför kommungränsen) på punkten.
                var selectedData: ByteArray? = null
                for (grid in grids) {
                    val cell = grid.readCellAtMercator(xMerc, yMerc) ?: continue
                    if (selectedData == null) {
                        selectedData = cell
                    }
                    val hasData = cell.any { (it.toInt() and 0xFF) > 0 }
                    if (hasData) {
                        selectedData = cell
                        break
                    }
                }

                val data = selectedData ?: return null
                val gran = data[0].toInt() and 0xFF
                val tall = data[1].toInt() and 0xFF
                val lov = data[2].toInt() and 0xFF
                val age = data[3].toInt() and 0xFF
                val fukt = data[4].toInt() and 0xFF
                val score = data[5].toInt() and 0xFF
                val total = gran + tall + lov

                val dominant = when {
                    fukt == 0 && total == 0 -> "Vatten / Utanför kommungräns"
                    total < 35 && age in 1..24 -> "Kalhygge / Ungskog"
                    total == 0 && age == 0 -> "Öppen mark / Bebyggelse"
                    total < 35 -> "Gles skog / Ungskog"
                    gran >= tall && gran >= lov && gran.toDouble() / total >= 0.45 -> "Grandominerad skog"
                    tall >= gran && tall >= lov && tall.toDouble() / total >= 0.45 -> "Talldominerad skog"
                    lov >= gran && lov >= tall && lov.toDouble() / total >= 0.45 -> "Lövdominerad skog"
                    else -> "Blandskog"
                }

                val motivering = buildString {
                    when {
                        score >= 80 -> append("Mycket hög potential för trattkantarell! ")
                        score >= 40 -> append("Goda förutsättningar för trattkantarell. ")
                        fukt == 0 && total == 0 -> append("Ingen skogsmark här (öppet vatten eller utanför kartområdet).")
                        total < 35 && age in 1..24 -> append("Avverkat kalhygge eller ungskog ($age år). Undvik för trattkantarell.")
                        total == 0 && age == 0 -> append("Ej skogsmark enligt NMD 2023 (t.ex. bebyggelse, åker eller hällmark).")
                        age in 1..49 -> append("Skogen är för ung ($age år, minst 50 år krävs). ")
                        total < 150 -> append("För låg virkesvolym ($total m³/ha, minst 150 m³/ha krävs). ")
                        gran < 40 -> append("För lite gran i beståndet ($gran m³/ha). ")
                        fukt == 1 -> append("Marken är för torr (Klass 1: Torr–frisk mark). ")
                        fukt == 4 -> append("Marken är för blöt (Klass 4: Sankmark/kärr). ")
                        else -> append("Uppfyller ej samtliga krav på sammanhängande barrskog. ")
                    }

                    if (total >= 35) {
                        append("Ålder: $age år. Trädvolym: $total m³/ha. ")
                        if (gran >= 100) append("Rikligt med gran ($gran m³/ha). ")
                        if (fukt == 2) append("Optimal markfuktighet (Frisk–fuktig).")
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
            try {
                it.raf.close()
            } catch (e: Exception) {
            }
        }
        grids.clear()
    }
}
