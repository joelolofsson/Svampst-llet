package se.svampradar.app

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val prefManager = remember { PreferencesManager(context) }
    val mapType by prefManager.mapTypeFlow.collectAsState(initial = "Liberty")
    val defaultMushroom by prefManager.defaultMushroomFlow.collectAsState(initial = false)
    val coroutineScope = rememberCoroutineScope()

    Column(modifier = modifier.fillMaxSize()) {
        Text(
            text = "Inställningar",
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.padding(16.dp)
        )

        ListItem(
            headlineContent = { Text("Karttyp") },
            supportingContent = {
                val mapOptions = listOf("Liberty", "Positron", "Bright", "Dark", "OpenTopoMap")
                Column(Modifier.selectableGroup()) {
                    mapOptions.forEach { text ->
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .selectable(
                                    selected = (text == mapType),
                                    onClick = { coroutineScope.launch { prefManager.saveMapType(text) } },
                                    role = Role.RadioButton
                                )
                                .padding(vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            RadioButton(
                                selected = (text == mapType),
                                onClick = null
                            )
                            Text(
                                text = text,
                                modifier = Modifier.padding(start = 16.dp)
                            )
                        }
                    }
                }
            }
        )

        HorizontalDivider()

        ListItem(
            headlineContent = { Text("Standard Svamp-toggle") },
            supportingContent = { Text("Visa Trattkantarell som standard när appen startas") },
            trailingContent = {
                Switch(
                    checked = defaultMushroom,
                    onCheckedChange = { isChecked ->
                        coroutineScope.launch { prefManager.saveDefaultMushroomToggle(isChecked) }
                    }
                )
            }
        )

        HorizontalDivider()

        ListItem(
            headlineContent = { Text("Om") },
            supportingContent = { 
                Text("SvampRadar v1.1\nDatakällor: OpenFreeMap, OpenTopoMap, MapLibre\nSvampdata: Lokal MBTiles") 
            }
        )
    }
}
