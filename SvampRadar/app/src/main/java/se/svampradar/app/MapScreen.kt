package se.svampradar.app

import android.Manifest
import android.content.pm.PackageManager
import android.util.Log
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.delay
import org.maplibre.android.camera.CameraPosition
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.location.LocationComponentActivationOptions
import org.maplibre.android.location.modes.CameraMode
import org.maplibre.android.location.modes.RenderMode
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.Style
import org.maplibre.android.style.layers.PropertyFactory.visibility
import org.maplibre.android.style.layers.PropertyFactory.rasterOpacity
import org.maplibre.android.style.layers.Property.VISIBLE
import org.maplibre.android.style.layers.Property.NONE
import org.maplibre.android.style.layers.RasterLayer
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MapScreen(
    modifier: Modifier = Modifier,
    viewModel: MapViewModel = viewModel()
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val prefManager = remember { PreferencesManager(context) }

    val isTrattkantarellActive by viewModel.isTrattkantarellActive.collectAsState()
    val isGulKantarellActive by viewModel.isGulKantarellActive.collectAsState()
    val userMapType by prefManager.mapTypeFlow.collectAsState(initial = "Liberty")

    var mapLibreMap by remember { mutableStateOf<MapLibreMap?>(null) }
    var selectedLocation by remember { mutableStateOf<LatLng?>(null) }

    var locationPermissionGranted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.ACCESS_FINE_LOCATION
            ) == PackageManager.PERMISSION_GRANTED
        )
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        locationPermissionGranted = permissions[Manifest.permission.ACCESS_FINE_LOCATION] == true ||
                permissions[Manifest.permission.ACCESS_COARSE_LOCATION] == true
    }

    LaunchedEffect(Unit) {
        if (!locationPermissionGranted) {
            permissionLauncher.launch(
                arrayOf(
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION
                )
            )
        }
    }

    val mbtilesServer = remember { 
        MBTilesTileSource(context).also { it.start() }
    }
    var isOnline by remember { mutableStateOf(NetworkHelper.isNetworkAvailable(context)) }

    LaunchedEffect(Unit) {
        while (true) {
            isOnline = NetworkHelper.isNetworkAvailable(context)
            delay(5000)
        }
    }

    val isDarkTheme = isSystemInDarkTheme()
    val mapType = if (!isOnline) "OfflineBase" else if (isDarkTheme) "Dark" else userMapType

    val mapView = remember {
        MapView(context).apply {
            getMapAsync { map ->
                mapLibreMap = map
                map.uiSettings.isCompassEnabled = true
                
                map.addOnMapLongClickListener { point ->
                    selectedLocation = point
                    true
                }

                map.cameraPosition = CameraPosition.Builder()
                    .target(LatLng(58.13, 12.15))
                    .zoom(11.0)
                    .build()
            }
        }
    }
    
    // Update map style when mapType changes
    LaunchedEffect(mapLibreMap, mapType, locationPermissionGranted) {
        val map = mapLibreMap ?: return@LaunchedEffect
        
        val styleStr = when(mapType) {
            "Liberty" -> "https://tiles.openfreemap.org/styles/liberty"
            "Satellit" -> """
                {
                  "version": 8,
                  "sources": {
                    "satellite": {
                      "type": "raster",
                      "tiles": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
                      "tileSize": 256
                    }
                  },
                  "layers": [
                    {
                      "id": "satellite",
                      "type": "raster",
                      "source": "satellite",
                      "minzoom": 0,
                      "maxzoom": 22
                    }
                  ]
                }
            """.trimIndent()
            "Positron" -> "https://tiles.openfreemap.org/styles/positron"
            "Bright" -> "https://tiles.openfreemap.org/styles/bright"
            "Dark" -> "https://tiles.openfreemap.org/styles/dark"
            "OpenTopoMap" -> """
                {
                  "version": 8,
                  "sources": {
                    "osm": {
                      "type": "raster",
                      "tiles": ["https://tile.opentopomap.org/{z}/{x}/{y}.png"],
                      "tileSize": 256
                    }
                  },
                  "layers": [
                    {
                      "id": "osm",
                      "type": "raster",
                      "source": "osm",
                      "minzoom": 0,
                      "maxzoom": 22
                    }
                  ]
                }
            """.trimIndent()
            "OfflineBase" -> """
                {
                  "version": 8,
                  "sources": {
                    "basemap": {
                      "type": "raster",
                      "tiles": ["http://127.0.0.1:${mbtilesServer.actualPort}/basemap/{z}/{x}/{y}.png"],
                      "tileSize": 256
                    }
                  },
                  "layers": [
                    {
                      "id": "basemap",
                      "type": "raster",
                      "source": "basemap",
                      "minzoom": 0,
                      "maxzoom": 22
                    }
                  ]
                }
            """.trimIndent()
            else -> "https://tiles.openfreemap.org/styles/liberty"
        }

        Log.i("SvampRadar", "Setting map style: $mapType (server port: ${mbtilesServer.actualPort})")
        if (styleStr.startsWith("{")) {
            map.setStyle(Style.Builder().fromJson(styleStr)) { style ->
                Log.i("SvampRadar", "Style loaded (JSON), setting up layers...")
                setupLayers(map, style, mbtilesServer, locationPermissionGranted, context)
            }
        } else {
            map.setStyle(styleStr) { style ->
                Log.i("SvampRadar", "Style loaded (URL: $mapType), setting up layers...")
                setupLayers(map, style, mbtilesServer, locationPermissionGranted, context)
            }
        }
    }

    LaunchedEffect(isTrattkantarellActive, mapLibreMap) {
        mapLibreMap?.style?.getLayer("layer_trattkantarell")?.setProperties(
            visibility(if (isTrattkantarellActive) VISIBLE else NONE)
        )
    }

    LaunchedEffect(isGulKantarellActive, mapLibreMap) {
        mapLibreMap?.style?.getLayer("layer_gulkantarell")?.setProperties(
            visibility(if (isGulKantarellActive) VISIBLE else NONE)
        )
    }

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> mapView.onStart()
                Lifecycle.Event.ON_RESUME -> mapView.onResume()
                Lifecycle.Event.ON_PAUSE -> mapView.onPause()
                Lifecycle.Event.ON_STOP -> mapView.onStop()
                Lifecycle.Event.ON_DESTROY -> mapView.onDestroy()
                else -> {}
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            mbtilesServer.stop()
            lifecycleOwner.lifecycle.removeObserver(observer)
        }
    }

    Box(modifier = modifier.fillMaxSize()) {
        AndroidView(
            factory = { mapView },
            modifier = Modifier.fillMaxSize()
        )

        Row(
            modifier = Modifier
                .align(Alignment.TopCenter)
                .padding(16.dp)
        ) {
            Card(
                elevation = CardDefaults.cardElevation(defaultElevation = 6.dp),
                shape = RoundedCornerShape(24.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
            ) {
                Row(modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)) {
                    FilterChip(
                        selected = isTrattkantarellActive,
                        onClick = { viewModel.toggleTrattkantarell() },
                        label = { Text("🍄 Trattkantarell") },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = MaterialTheme.colorScheme.primaryContainer,
                            selectedLabelColor = MaterialTheme.colorScheme.onPrimaryContainer
                        )
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    FilterChip(
                        selected = isGulKantarellActive,
                        onClick = { viewModel.toggleGulKantarell() },
                        label = { Text("🍄 Gul kantarell") },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = MaterialTheme.colorScheme.primaryContainer,
                            selectedLabelColor = MaterialTheme.colorScheme.onPrimaryContainer
                        )
                    )
                }
            }
        }

        if (!isOnline) {
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .padding(16.dp)
            ) {
                Text(
                    text = "Offline",
                    color = MaterialTheme.colorScheme.onErrorContainer,
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                    style = MaterialTheme.typography.labelSmall
                )
            }
        }

        FloatingActionButton(
            onClick = {
                if (locationPermissionGranted) {
                    mapLibreMap?.locationComponent?.lastKnownLocation?.let { location ->
                        mapLibreMap?.animateCamera(
                            CameraUpdateFactory.newLatLngZoom(
                                LatLng(location.latitude, location.longitude),
                                14.0
                            )
                        )
                    }
                } else {
                    permissionLauncher.launch(
                        arrayOf(
                            Manifest.permission.ACCESS_FINE_LOCATION,
                            Manifest.permission.ACCESS_COARSE_LOCATION
                        )
                    )
                }
            },
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(16.dp),
            containerColor = MaterialTheme.colorScheme.tertiaryContainer,
            contentColor = MaterialTheme.colorScheme.onTertiaryContainer
        ) {
            Icon(Icons.Filled.LocationOn, contentDescription = "Center Map")
        }
    }

    selectedLocation?.let { location ->
        DetailBottomSheet(
            location = location,
            onDismissRequest = { selectedLocation = null }
        )
    }
}

private fun setupLayers(
    mapLibreMap: MapLibreMap,
    style: Style,
    mbtilesServer: MBTilesTileSource,
    granted: Boolean,
    context: android.content.Context
) {
    if (granted) {
        val locationComponent = mapLibreMap.locationComponent
        val locationComponentActivationOptions =
            LocationComponentActivationOptions.builder(context, style)
                .useDefaultLocationEngine(true)
                .build()
        locationComponent.activateLocationComponent(locationComponentActivationOptions)
        try {
            locationComponent.isLocationComponentEnabled = true
            locationComponent.cameraMode = CameraMode.TRACKING
            locationComponent.renderMode = RenderMode.COMPASS
        } catch (e: SecurityException) {
            e.printStackTrace()
        }
    }

    val sourceTratt = mbtilesServer.createRasterSource("source_trattkantarell", "trattkantarell")
    if (style.getSource("source_trattkantarell") == null) {
        style.addSource(sourceTratt)
    }
    if (style.getLayer("layer_trattkantarell") == null) {
        style.addLayer(RasterLayer("layer_trattkantarell", "source_trattkantarell").withProperties(
            visibility(VISIBLE),
            rasterOpacity(0.6f)
        ))
    }

    val sourceGul = mbtilesServer.createRasterSource("source_gulkantarell", "gulkantarell")
    if (style.getSource("source_gulkantarell") == null) {
        style.addSource(sourceGul)
    }
    if (style.getLayer("layer_gulkantarell") == null) {
        style.addLayer(RasterLayer("layer_gulkantarell", "source_gulkantarell").withProperties(
            visibility(NONE),
            rasterOpacity(0.6f)
        ))
    }
}
