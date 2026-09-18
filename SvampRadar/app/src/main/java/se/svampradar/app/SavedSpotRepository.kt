package se.svampradar.app

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext

class SavedSpotRepository(context: Context) : SQLiteOpenHelper(context, "saved_spots.db", null, 1) {

    private val _spotsFlow = MutableStateFlow<List<SavedSpot>>(emptyList())
    val spotsFlow: StateFlow<List<SavedSpot>> = _spotsFlow.asStateFlow()

    init {
        loadSpots()
    }

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """
            CREATE TABLE spots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                mushroom_type TEXT,
                amount TEXT,
                note TEXT,
                date TEXT,
                latitude REAL,
                longitude REAL
            )
            """.trimIndent()
        )
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        db.execSQL("DROP TABLE IF EXISTS spots")
        onCreate(db)
    }

    fun loadSpots() {
        val list = mutableListOf<SavedSpot>()
        val db = readableDatabase
        val cursor = db.rawQuery("SELECT id, title, mushroom_type, amount, note, date, latitude, longitude FROM spots ORDER BY id DESC", null)
        cursor.use {
            while (it.moveToNext()) {
                list.add(
                    SavedSpot(
                        id = it.getLong(0),
                        title = it.getString(1) ?: "",
                        mushroomType = it.getString(2) ?: "Trattkantarell",
                        amount = it.getString(3) ?: "",
                        note = it.getString(4) ?: "",
                        date = it.getString(5) ?: "",
                        latitude = it.getDouble(6),
                        longitude = it.getDouble(7)
                    )
                )
            }
        }
        _spotsFlow.value = list
    }

    suspend fun addSpot(spot: SavedSpot): Long = withContext(Dispatchers.IO) {
        val db = writableDatabase
        val values = ContentValues().apply {
            put("title", spot.title)
            put("mushroom_type", spot.mushroomType)
            put("amount", spot.amount)
            put("note", spot.note)
            put("date", spot.date)
            put("latitude", spot.latitude)
            put("longitude", spot.longitude)
        }
        val id = db.insert("spots", null, values)
        loadSpots()
        id
    }

    suspend fun deleteSpot(id: Long) = withContext(Dispatchers.IO) {
        val db = writableDatabase
        db.delete("spots", "id = ?", arrayOf(id.toString()))
        loadSpots()
    }
}
