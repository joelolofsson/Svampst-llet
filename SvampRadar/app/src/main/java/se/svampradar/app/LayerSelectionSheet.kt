package se.svampradar.app

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LayerSelectionSheet(
    currentMapType: String,
    onMapTypeSelected: (String) -> Unit,
    isTrattkantarellActive: Boolean,
    onToggleTrattkantarell: () -> Unit,
    isGulKantarellActive: Boolean,
    onToggleGulKantarell: () -> Unit,
    isSkogstypActive: Boolean,
    onToggleSkogstyp: () -> Unit,
    isMarkfuktighetActive: Boolean,
    onToggleMarkfuktighet: () -> Unit,
    isSavedSpotsActive: Boolean,
    onToggleSavedSpots: () -> Unit,
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    var selectedLegendLayer by remember { mutableStateOf<String?>(null) }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp, vertical = 8.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Karttyp och lager",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold
                )
                IconButton(onClick = onDismiss) {
                    Icon(Icons.Filled.Close, contentDescription = "Stäng")
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // 1. BASKARTA
            Text(
                text = "Baskarta",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary
            )
            Spacer(modifier = Modifier.height(8.dp))

            val mapOptions = listOf(
                "Satellit" to "Högupplösta satellitbilder (ESRI)",
                "Liberty" to "Topografisk terrängkarta",
                "Positron" to "Ljus minimalistisk karta"
            )

            mapOptions.forEach { (type, desc) ->
                Surface(
                    onClick = { onMapTypeSelected(type) },
                    shape = RoundedCornerShape(12.dp),
                    color = if (currentMapType == type) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RadioButton(
                            selected = (currentMapType == type),
                            onClick = { onMapTypeSelected(type) }
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text(text = type, fontWeight = FontWeight.Bold)
                            Text(text = desc, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // 2. KARTLAGER
            Text(
                text = "Kartlager",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary
            )
            Spacer(modifier = Modifier.height(8.dp))

            // TRATTKANTARELL
            LayerItem(
                title = "Trattkantarell (Hotspots)",
                description = "Äldre barr- och blandskog med optimal fuktighet",
                isChecked = isTrattkantarellActive,
                onCheckedChange = { onToggleTrattkantarell() },
                onInfoClick = { selectedLegendLayer = "trattkantarell" }
            )

            // GUL KANTARELL (TEASER)
            LayerItem(
                title = "Gul kantarell (Hotspots)",
                description = "Kommer snart • Algoritm under utveckling",
                isChecked = false,
                enabled = false,
                onDisabledClick = {
                    Toast.makeText(context, "Gul kantarell kommer i en framtida uppdatering!", Toast.LENGTH_SHORT).show()
                },
                onCheckedChange = { },
                onInfoClick = { selectedLegendLayer = "gulkantarell" }
            )

            // SKOGSTYP
            LayerItem(
                title = "Skogstyp och kalhyggen",
                description = "Gran, tall, löv samt blåmarkerade kalhyggen",
                isChecked = isSkogstypActive,
                onCheckedChange = { onToggleSkogstyp() },
                onInfoClick = { selectedLegendLayer = "skogstyp" }
            )

            // MARKFUKTIGHET
            LayerItem(
                title = "Markfuktighet (SLU DTW)",
                description = "Fuktklasser från torr mark till sankmark",
                isChecked = isMarkfuktighetActive,
                onCheckedChange = { onToggleMarkfuktighet() },
                onInfoClick = { selectedLegendLayer = "markfuktighet" }
            )

            // SPARADE STÄLLEN
            LayerItem(
                title = "Sparade ställen",
                description = "Visa dina personliga fyndmarkeringar",
                isChecked = isSavedSpotsActive,
                onCheckedChange = { onToggleSavedSpots() },
                onInfoClick = null
            )

            Spacer(modifier = Modifier.height(24.dp))
        }
    }

    selectedLegendLayer?.let { layerKey ->
        LegendDialog(
            layerKey = layerKey,
            onDismiss = { selectedLegendLayer = null }
        )
    }
}

@Composable
private fun LayerItem(
    title: String,
    description: String,
    isChecked: Boolean,
    enabled: Boolean = true,
    onDisabledClick: (() -> Unit)? = null,
    onCheckedChange: (Boolean) -> Unit,
    onInfoClick: (() -> Unit)?
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .then(
                if (!enabled && onDisabledClick != null) {
                    Modifier.clickable { onDisabledClick() }
                } else {
                    Modifier
                }
            )
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = title, 
                    fontWeight = FontWeight.SemiBold,
                    color = if (enabled) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                )
                if (onInfoClick != null) {
                    IconButton(onClick = onInfoClick, modifier = Modifier.size(28.dp)) {
                        Icon(
                            Icons.Filled.Info,
                            contentDescription = "Förklaring",
                            modifier = Modifier.size(18.dp),
                            tint = if (enabled) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f)
                        )
                    }
                }
            }
            Text(
                text = description, 
                style = MaterialTheme.typography.bodySmall, 
                color = if (enabled) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f)
            )
        }
        Switch(
            checked = isChecked,
            onCheckedChange = if (enabled) onCheckedChange else null,
            enabled = enabled
        )
    }
}

@Composable
fun LegendDialog(
    layerKey: String,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Text(
                when (layerKey) {
                    "skogstyp" -> "Färgförklaring: Skogstyp"
                    "markfuktighet" -> "Färgförklaring: Markfuktighet"
                    "trattkantarell" -> "Färgförklaring: Trattkantarell"
                    "gulkantarell" -> "Färgförklaring: Gul kantarell"
                    else -> "Förklaring"
                }
            )
        },
        text = {
            Column(modifier = Modifier.fillMaxWidth()) {
                when (layerKey) {
                    "skogstyp" -> {
                        LegendRow(color = Color(0xFF1E88E5), label = "Blå", desc = "Kalhygge / Ungskog (< 25 år). Undvik dessa områden.")
                        LegendRow(color = Color(0xFF2E7D32), label = "Mörkgrön", desc = "Grandominerad skog (> 45% gran).")
                        LegendRow(color = Color(0xFFE65100), label = "Orange", desc = "Talldominerad skog (> 45% tall).")
                        LegendRow(color = Color(0xFF7CB342), label = "Ljusgrön", desc = "Lövdominerad skog (> 45% löv).")
                        LegendRow(color = Color(0xFF9E9D24), label = "Olivgrön", desc = "Blandskog (blandade trädslag).")
                    }
                    "markfuktighet" -> {
                        LegendRow(color = Color(0xFFE6B43C), label = "Gul", desc = "Klass 1: Torr–frisk mark (bergshällar och åsar).")
                        LegendRow(color = Color(0xFF50C8F0), label = "Turkos", desc = "Klass 2: Frisk–fuktig mark (optimal fukt för svamp).")
                        LegendRow(color = Color(0xFF1E6EE6), label = "Mellanblå", desc = "Klass 3: Fuktig–blöt mark (raviner och sänkor).")
                        LegendRow(color = Color(0xFF0A1EA0), label = "Mörkblå", desc = "Klass 4: Vatten / Sankmark och kärr.")
                    }
                    "trattkantarell", "gulkantarell" -> {
                        LegendRow(color = Color(0xFFD32F2F), label = "Mörkröd", desc = "Mycket hög potential (äldre skog, hög volym och perfekt fuktighet).")
                        LegendRow(color = Color(0xFFF57C00), label = "Orange", desc = "God potential (uppfyller samtliga biologiska grundkrav).")
                        LegendRow(color = Color(0xFFFFB74D), label = "Ljusorange", desc = "Måttlig potential.")
                    }
                }
            }
        },
        confirmButton = {
            Button(onClick = onDismiss) {
                Text("Stäng")
            }
        }
    )
}

@Composable
private fun LegendRow(color: Color, label: String, desc: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.Top
    ) {
        Box(
            modifier = Modifier
                .size(18.dp)
                .clip(RoundedCornerShape(4.dp))
                .background(color)
        )
        Spacer(modifier = Modifier.width(12.dp))
        Column {
            Text(text = label, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium)
            Text(text = desc, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
