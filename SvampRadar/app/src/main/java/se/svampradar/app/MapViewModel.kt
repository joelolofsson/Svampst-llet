package se.svampradar.app

import androidx.lifecycle.ViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class MapViewModel : ViewModel() {
    private val _isTrattkantarellActive = MutableStateFlow(true)
    val isTrattkantarellActive: StateFlow<Boolean> = _isTrattkantarellActive.asStateFlow()

    private val _isGulKantarellActive = MutableStateFlow(false)
    val isGulKantarellActive: StateFlow<Boolean> = _isGulKantarellActive.asStateFlow()

    private val _isMarkfuktighetActive = MutableStateFlow(false)
    val isMarkfuktighetActive: StateFlow<Boolean> = _isMarkfuktighetActive.asStateFlow()

    private val _isSkogstypActive = MutableStateFlow(false)
    val isSkogstypActive: StateFlow<Boolean> = _isSkogstypActive.asStateFlow()

    private val _isSavedSpotsActive = MutableStateFlow(true)
    val isSavedSpotsActive: StateFlow<Boolean> = _isSavedSpotsActive.asStateFlow()

    // Om ett specifikt ställe valts från listan för att fokuseras och visas ensamt
    private val _selectedSpotForMap = MutableStateFlow<SavedSpot?>(null)
    val selectedSpotForMap: StateFlow<SavedSpot?> = _selectedSpotForMap.asStateFlow()

    fun toggleTrattkantarell() {
        _isTrattkantarellActive.value = !_isTrattkantarellActive.value
    }

    fun toggleGulKantarell() {
        _isGulKantarellActive.value = !_isGulKantarellActive.value
    }

    fun toggleMarkfuktighet() {
        _isMarkfuktighetActive.value = !_isMarkfuktighetActive.value
    }

    fun toggleSkogstyp() {
        _isSkogstypActive.value = !_isSkogstypActive.value
    }

    fun toggleSavedSpots() {
        _isSavedSpotsActive.value = !_isSavedSpotsActive.value
    }

    fun focusOnSpot(spot: SavedSpot) {
        _selectedSpotForMap.value = spot
    }

    fun clearSpotFilter() {
        _selectedSpotForMap.value = null
    }
}
