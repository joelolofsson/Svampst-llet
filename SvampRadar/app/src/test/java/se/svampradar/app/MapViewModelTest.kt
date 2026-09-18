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
        assertEquals(false, initial)

        viewModel.toggleTrattkantarell()
        assertEquals(true, viewModel.isTrattkantarellActive.value)

        viewModel.toggleTrattkantarell()
        assertEquals(false, viewModel.isTrattkantarellActive.value)
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
}
