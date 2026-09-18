package se.svampradar.app

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "settings")

class PreferencesManager(private val context: Context) {
    companion object {
        val MAP_TYPE_KEY = stringPreferencesKey("map_type")
        val DEFAULT_MUSHROOM_KEY = booleanPreferencesKey("default_mushroom_toggle")
    }

    val mapTypeFlow: Flow<String> = context.dataStore.data.map { preferences ->
        preferences[MAP_TYPE_KEY] ?: "Liberty"
    }

    val defaultMushroomFlow: Flow<Boolean> = context.dataStore.data.map { preferences ->
        preferences[DEFAULT_MUSHROOM_KEY] ?: false
    }

    suspend fun saveMapType(type: String) {
        context.dataStore.edit { preferences ->
            preferences[MAP_TYPE_KEY] = type
        }
    }

    suspend fun saveDefaultMushroomToggle(enabled: Boolean) {
        context.dataStore.edit { preferences ->
            preferences[DEFAULT_MUSHROOM_KEY] = enabled
        }
    }
}
