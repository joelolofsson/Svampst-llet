package se.svampradar.app

import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import org.maplibre.android.geometry.LatLng
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DetailBottomSheet(
    location: LatLng,
    inspector: ForestDataInspector,
    savedSpotRepo: SavedSpotRepository,
    onDismissRequest: () -> Unit
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    val inspection = remember(location) {
        inspector.inspect(location.latitude, location.longitude)
    }

    var showSaveDialog by remember { mutableStateOf(false) }

    ModalBottomSheet(
        onDismissRequest = onDismissRequest,
        sheetState = sheetState
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp, vertical = 10.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "Skogsinspektion",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = String.format(Locale.US, "GPS: %.5f, %.5f", location.latitude, location.longitude),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                if (inspection != null) {
                    val scoreColor = when {
                        inspection.score >= 70 -> Color(0xFFD32F2F)
                        inspection.score >= 40 -> Color(0xFFF57C00)
                        else -> Color(0xFF757575)
                    }
                    Surface(
                        color = scoreColor.copy(alpha = 0.15f),
                        shape = RoundedCornerShape(16.dp),
                        border = androidx.compose.foundation.BorderStroke(1.dp, scoreColor)
                    ) {
                        Text(
                            text = "${inspection.score} p",
                            color = scoreColor,
                            fontWeight = FontWeight.ExtraBold,
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                            style = MaterialTheme.typography.titleMedium
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // MOTIVERING
            if (inspection != null) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = "Motivering och analys",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = inspection.motivation,
                            style = MaterialTheme.typography.bodyMedium
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        HorizontalDivider()
                        Spacer(modifier = Modifier.height(12.dp))

                        DetailRow(label = "Skogstyp", value = inspection.dominantSpecies)
                        DetailRow(label = "Skogens ålder", value = "${inspection.age} år")
                        DetailRow(
                            label = "Markfuktighet",
                            value = when (inspection.moistureClass) {
                                1 -> "Torr–frisk mark (Klass 1)"
                                2 -> "Frisk–fuktig mark (Klass 2, Optimal)"
                                3 -> "Fuktig–blöt mark (Klass 3)"
                                4 -> "Vatten / Sankmark (Klass 4)"
                                else -> "Ingen data"
                            }
                        )
                        DetailRow(
                            label = "Trädvolym",
                            value = "${inspection.totalVol} m³/ha (Gran: ${inspection.granVol}, Tall: ${inspection.tallVol}, Löv: ${inspection.lovVol})"
                        )
                    }
                }
            } else {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
                ) {
                    Text(
                        text = "Ingen skogsdata tillgänglig för denna koordinat.",
                        modifier = Modifier.padding(16.dp),
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // ACTION BUTTONS
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Button(
                    onClick = {
                        val lat = location.latitude
                        val lon = location.longitude
                        val navUri = Uri.parse("google.navigation:q=$lat,$lon")
                        val mapIntent = Intent(Intent.ACTION_VIEW, navUri).apply {
                            setPackage("com.google.android.apps.maps")
                        }
                        try {
                            context.startActivity(mapIntent)
                        } catch (e: Exception) {
                            val fallbackUri = Uri.parse("https://www.google.com/maps/dir/?api=1&destination=$lat,$lon")
                            context.startActivity(Intent(Intent.ACTION_VIEW, fallbackUri))
                        }
                    },
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                ) {
                    Icon(Icons.Filled.Navigation, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("Navigera")
                }

                OutlinedButton(
                    onClick = {
                        val lat = location.latitude
                        val lon = location.longitude
                        val shareText = "Kolla in den här platsen i skogen:\nhttps://maps.google.com/?q=$lat,$lon"
                        val shareIntent = Intent(Intent.ACTION_SEND).apply {
                            type = "text/plain"
                            putExtra(Intent.EXTRA_SUBJECT, "SvampRadar Plats")
                            putExtra(Intent.EXTRA_TEXT, shareText)
                        }
                        context.startActivity(Intent.createChooser(shareIntent, "Dela plats via"))
                    },
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(Icons.Filled.Share, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("Dela")
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            Button(
                onClick = { showSaveDialog = true },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.secondaryContainer,
                    contentColor = MaterialTheme.colorScheme.onSecondaryContainer
                )
            ) {
                Icon(Icons.Filled.BookmarkAdd, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(modifier = Modifier.width(8.dp))
                Text("Spara plats", fontWeight = FontWeight.Bold)
            }

            Spacer(modifier = Modifier.height(24.dp))
        }
    }

    if (showSaveDialog) {
        SaveSpotDialog(
            location = location,
            onDismiss = { showSaveDialog = false },
            onSave = { spot ->
                coroutineScope.launch {
                    savedSpotRepo.addSpot(spot)
                    Toast.makeText(context, "Platsen har sparats", Toast.LENGTH_SHORT).show()
                    showSaveDialog = false
                }
            }
        )
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.Top
    ) {
        Column {
            Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
        }
    }
}

@Composable
fun SaveSpotDialog(
    location: LatLng,
    onDismiss: () -> Unit,
    onSave: (SavedSpot) -> Unit
) {
    var title by remember { mutableStateOf("") }
    var mushroomType by remember { mutableStateOf("Trattkantarell") }
    var amount by remember { mutableStateOf("Rikligt") }
    var note by remember { mutableStateOf("") }

    val mushroomTypes = listOf("Trattkantarell", "Gul kantarell", "Karljohan", "Annat")
    val amounts = listOf("Rikligt", "Måttligt", "Lite")

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Spara plats") },
        text = {
            Column(modifier = Modifier.fillMaxWidth()) {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("Namn på stället (t.ex. Vid bäcken)") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
                Spacer(modifier = Modifier.height(12.dp))

                Text("Svampart:", style = MaterialTheme.typography.labelMedium)
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    mushroomTypes.forEach { type ->
                        FilterChip(
                            selected = mushroomType == type,
                            onClick = { mushroomType = type },
                            label = { Text(type, style = MaterialTheme.typography.bodySmall) }
                        )
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))
                Text("Mängd:", style = MaterialTheme.typography.labelMedium)
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    amounts.forEach { a ->
                        FilterChip(
                            selected = amount == a,
                            onClick = { amount = a },
                            label = { Text(a, style = MaterialTheme.typography.bodySmall) }
                        )
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))
                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it },
                    label = { Text("Anteckning (frivillig)") },
                    modifier = Modifier.fillMaxWidth(),
                    maxLines = 3
                )
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    val finalTitle = if (title.isBlank()) "$mushroomType vid ${String.format(Locale.US, "%.3f", location.latitude)}" else title
                    val dateStr = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())
                    onSave(
                        SavedSpot(
                            title = finalTitle,
                            mushroomType = mushroomType,
                            amount = amount,
                            note = note,
                            date = dateStr,
                            latitude = location.latitude,
                            longitude = location.longitude
                        )
                    )
                }
            ) {
                Text("Spara")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Avbryt")
            }
        }
    )
}
