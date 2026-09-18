package se.svampradar.app

import android.Manifest
import android.content.pm.PackageManager
import android.util.Log
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Layers
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.maplibre.android.annotations.MarkerOptions
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MapScreen(
    modifier: Modifier = Modifier,
    viewModel: MapViewModel = viewModel()
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val coroutineScope = rememberCoroutineScope()
    val prefManager = remember { PreferencesManager(context) }
    val inspector = remember { ForestDataInspector(context) }
    val savedSpotRepo = remember { SavedSpotRepository(context) }

    val isTrattkantarellActive by viewModel.isTrattkantarellActive.collectAsState()
    val isGulKantarellActive by viewModel.isGulKantarellActive.collectAsState()
    val isMarkfuktighetActive by viewModel.isMarkfuktighetActive.collectAsState()
    val isSkogstypActive by viewModel.isSkogstypActive.collectAsState()
    val isSavedSpotsActive by viewModel.isSavedSpotsActive.collectAsState()
    val selectedSpotForMap by viewModel.selectedSpotForMap.collectAsState()
    val savedSpots by savedSpotRepo.spotsFlow.collectAsState()

    val userMapType by prefManager.mapTypeFlow.collectAsState(initial = "Satellit")
    var showLayerSheet by remember { mutableStateOf(false) }

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
    val mapType = if (!isOnline) "OfflineBase" else if (isDarkTheme && userMapType == "Liberty") "Dark" else userMapType

    val mapView = remember {
        MapView(context).apply {
            getMapAsync { map ->
                mapLibreMap = map
                map.uiSettings.isCompassEnabled = true
                
                map.addOnMapClickListener { point ->
                    selectedLocation = point
                    true
                }

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
            "Liberty" -> "https://tiles.openfreemap.org/styles/liberty"
            "Positron" -> "https://tiles.openfreemap.org/styles/positron"
            "Dark" -> "https://tiles.openfreemap.org/styles/dark"
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

    LaunchedEffect(isMarkfuktighetActive, mapLibreMap) {
        mapLibreMap?.style?.getLayer("layer_markfuktighet")?.setProperties(
            visibility(if (isMarkfuktighetActive) VISIBLE else NONE)
        )
    }

    LaunchedEffect(isSkogstypActive, mapLibreMap) {
        mapLibreMap?.style?.getLayer("layer_skogstyp")?.setProperties(
            visibility(if (isSkogstypActive) VISIBLE else NONE)
        )
    }

    // Rendera sparade svampmarkörer på kartan (styrs av isSavedSpotsActive och ev. filtrerat ställe)
    LaunchedEffect(savedSpots, isSavedSpotsActive, selectedSpotForMap, mapLibreMap) {
        val map = mapLibreMap ?: return@LaunchedEffect
        map.clear()

        if (!isSavedSpotsActive) {
            return@LaunchedEffect
        }

        if (selectedSpotForMap != null) {
            val spot = selectedSpotForMap!!
            map.addMarker(
                MarkerOptions()
                    .position(LatLng(spot.latitude, spot.longitude))
                    .title("${spot.title} (${spot.mushroomType})")
                    .snippet("${spot.amount} • ${spot.date}\n${spot.note}")
            )
            map.animateCamera(
                CameraUpdateFactory.newLatLngZoom(
                    LatLng(spot.latitude, spot.longitude),
                    15.0
                )
            )
        } else {
            savedSpots.forEach { spot ->
                map.addMarker(
                    MarkerOptions()
                        .position(LatLng(spot.latitude, spot.longitude))
                        .title("${spot.title} (${spot.mushroomType})")
                        .snippet("${spot.amount} • ${spot.date}\n${spot.note}")
                )
            }
        }
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
            inspector.close()
            savedSpotRepo.close()
            lifecycleOwner.lifecycle.removeObserver(observer)
        }
    }

    Box(modifier = modifier.fillMaxSize()) {
        AndroidView(
            factory = { mapView },
            modifier = Modifier.fillMaxSize()
        )

        // FILTER BANNER: Om en specifik plats valts från listan
        if (selectedSpotForMap != null) {
            Surface(
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .padding(top = 16.dp),
                shape = RoundedCornerShape(24.dp),
                color = MaterialTheme.colorScheme.surfaceVariant,
                shadowElevation = 4.dp
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "Visar enbart: ${selectedSpotForMap?.title}",
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    IconButton(
                        onClick = { viewModel.clearSpotFilter() },
                        modifier = Modifier.size(24.dp)
                    ) {
                        Icon(Icons.Filled.Close, contentDescription = "Visa alla platser", modifier = Modifier.size(16.dp))
                    }
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

        // FLOATING ACTION BUTTONS: Höger sida
        Column(
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            horizontalAlignment = Alignment.End
        ) {
            // LAGER-KNAPP
            FloatingActionButton(
                onClick = { showLayerSheet = true },
                containerColor = MaterialTheme.colorScheme.surfaceVariant,
                contentColor = MaterialTheme.colorScheme.onSurfaceVariant
            ) {
                Icon(Icons.Filled.Layers, contentDescription = "Karttyp och lager")
            }

            // GPS CENTRERA-KNAPP
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
                containerColor = MaterialTheme.colorScheme.tertiaryContainer,
                contentColor = MaterialTheme.colorScheme.onTertiaryContainer
            ) {
                Icon(Icons.Filled.LocationOn, contentDescription = "Centrera karta")
            }
        }
    }

    // LAGER- OCH KARTTYPSVAL (SHEET)
    if (showLayerSheet) {
        LayerSelectionSheet(
            currentMapType = userMapType,
            onMapTypeSelected = { type ->
                coroutineScope.launch {
                    prefManager.saveMapType(type)
                }
            },
            isTrattkantarellActive = isTrattkantarellActive,
            onToggleTrattkantarell = { viewModel.toggleTrattkantarell() },
            isGulKantarellActive = isGulKantarellActive,
            onToggleGulKantarell = { viewModel.toggleGulKantarell() },
            isSkogstypActive = isSkogstypActive,
            onToggleSkogstyp = { viewModel.toggleSkogstyp() },
            isMarkfuktighetActive = isMarkfuktighetActive,
            onToggleMarkfuktighet = { viewModel.toggleMarkfuktighet() },
            isSavedSpotsActive = isSavedSpotsActive,
            onToggleSavedSpots = { viewModel.toggleSavedSpots() },
            onDismiss = { showLayerSheet = false }
        )
    }

    selectedLocation?.let { location ->
        DetailBottomSheet(
            location = location,
            inspector = inspector,
            savedSpotRepo = savedSpotRepo,
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

    val sourceSkog = mbtilesServer.createRasterSource("source_skogstyp", "skogstyp")
    if (style.getSource("source_skogstyp") == null) {
        style.addSource(sourceSkog)
    }
    if (style.getLayer("layer_skogstyp") == null) {
        style.addLayer(RasterLayer("layer_skogstyp", "source_skogstyp").withProperties(
            visibility(NONE),
            rasterOpacity(0.55f)
        ))
    }

    val sourceFukt = mbtilesServer.createRasterSource("source_markfuktighet", "markfuktighet")
    if (style.getSource("source_markfuktighet") == null) {
        style.addSource(sourceFukt)
    }
    if (style.getLayer("layer_markfuktighet") == null) {
        style.addLayer(RasterLayer("layer_markfuktighet", "source_markfuktighet").withProperties(
            visibility(NONE),
            rasterOpacity(0.55f)
        ))
    }

    val sourceTratt = mbtilesServer.createRasterSource("source_trattkantarell", "trattkantarell")
    if (style.getSource("source_trattkantarell") == null) {
        style.addSource(sourceTratt)
    }
    if (style.getLayer("layer_trattkantarell") == null) {
        style.addLayer(RasterLayer("layer_trattkantarell", "source_trattkantarell").withProperties(
            visibility(VISIBLE),
            rasterOpacity(0.65f)
        ))
    }

    val sourceGul = mbtilesServer.createRasterSource("source_gulkantarell", "gulkantarell")
    if (style.getSource("source_gulkantarell") == null) {
        style.addSource(sourceGul)
    }
    if (style.getLayer("layer_gulkantarell") == null) {
        style.addLayer(RasterLayer("layer_gulkantarell", "source_gulkantarell").withProperties(
            visibility(NONE),
            rasterOpacity(0.65f)
        ))
    }
}
