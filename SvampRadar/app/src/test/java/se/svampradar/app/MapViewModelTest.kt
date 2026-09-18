package se.svampradar.app

import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

class MapViewModelTest {

    private lateinit var viewModel: MapViewModel

    @Before
    fun setup() {
        viewModel = MapViewModel()
    }

    @Test
    fun `toggleTrattkantarell flips state`() = runTest {
        val initial = viewModel.isTrattkantarellActive.value
        assertEquals(true, initial)

        viewModel.toggleTrattkantarell()
        assertEquals(false, viewModel.isTrattkantarellActive.value)

        viewModel.toggleTrattkantarell()
        assertEquals(true, viewModel.isTrattkantarellActive.value)
    }

    @Test
    fun `toggleGulKantarell flips state`() = runTest {
        val initial = viewModel.isGulKantarellActive.value
        assertEquals(false, initial)

        viewModel.toggleGulKantarell()
        assertEquals(true, viewModel.isGulKantarellActive.value)

        viewModel.toggleGulKantarell()
        assertEquals(false, viewModel.isGulKantarellActive.value)
    }

    @Test
    fun `toggleSkogstyp flips state`() = runTest {
        assertEquals(false, viewModel.isSkogstypActive.value)
        viewModel.toggleSkogstyp()
        assertEquals(true, viewModel.isSkogstypActive.value)
    }

    @Test
    fun `toggleMarkfuktighet flips state`() = runTest {
        assertEquals(false, viewModel.isMarkfuktighetActive.value)
        viewModel.toggleMarkfuktighet()
        assertEquals(true, viewModel.isMarkfuktighetActive.value)
    }

    @Test
    fun `toggleSavedSpots flips state`() = runTest {
        assertEquals(true, viewModel.isSavedSpotsActive.value)
        viewModel.toggleSavedSpots()
        assertEquals(false, viewModel.isSavedSpotsActive.value)
    }
}
