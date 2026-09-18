package se.svampradar.app

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class PreferencesManagerTest {

    private lateinit var preferencesManager: PreferencesManager
    private lateinit var context: Context

    @Before
    fun setup() {
        context = ApplicationProvider.getApplicationContext()
        preferencesManager = PreferencesManager(context)
    }

    @Test
    fun `default map type is Liberty`() = runTest {
        val defaultType = preferencesManager.mapTypeFlow.first()
        assertEquals("Liberty", defaultType)
    }

    @Test
    fun `save map type updates flow`() = runTest {
        preferencesManager.saveMapType("OpenTopoMap")
        val updatedType = preferencesManager.mapTypeFlow.first()
        assertEquals("OpenTopoMap", updatedType)
    }
}
