package se.svampradar.app

import androidx.lifecycle.ViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class MapViewModel : ViewModel() {
    private val _isTrattkantarellActive = MutableStateFlow(false)
    val isTrattkantarellActive: StateFlow<Boolean> = _isTrattkantarellActive.asStateFlow()

    private val _isGulKantarellActive = MutableStateFlow(false)
    val isGulKantarellActive: StateFlow<Boolean> = _isGulKantarellActive.asStateFlow()

    private val _isMarkfuktighetActive = MutableStateFlow(false)
    val isMarkfuktighetActive: StateFlow<Boolean> = _isMarkfuktighetActive.asStateFlow()

    fun toggleTrattkantarell() {
        _isTrattkantarellActive.value = !_isTrattkantarellActive.value
    }

    fun toggleGulKantarell() {
        _isGulKantarellActive.value = !_isGulKantarellActive.value
    }

    fun toggleMarkfuktighet() {
        _isMarkfuktighetActive.value = !_isMarkfuktighetActive.value
    }
}
