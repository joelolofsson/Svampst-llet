package se.svampradar.app

data class SavedSpot(
    val id: Long = 0,
    val title: String,
    val mushroomType: String, // "Trattkantarell", "Gul kantarell", "Karljohan", etc.
    val amount: String, // "Rikligt", "Måttligt", "Lite"
    val note: String,
    val date: String,
    val latitude: Double,
    val longitude: Double
)
