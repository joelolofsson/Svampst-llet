package se.svampradar.app

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

import androidx.compose.ui.res.stringResource

@Composable
fun SettingsScreen(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val prefManager = remember { PreferencesManager(context) }
    val defaultMushroom by prefManager.defaultMushroomFlow.collectAsState(initial = false)
    val coroutineScope = rememberCoroutineScope()

    Column(modifier = modifier.fillMaxSize()) {
        Text(
            text = stringResource(R.string.settings_title),
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.padding(16.dp)
        )

        ListItem(
            headlineContent = { Text(stringResource(R.string.settings_default_toggle)) },
            supportingContent = { Text(stringResource(R.string.settings_default_toggle_desc)) },
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
            headlineContent = { Text(stringResource(R.string.settings_coverage_title)) },
            supportingContent = { 
                Text(stringResource(R.string.settings_coverage_desc)) 
            }
        )

        HorizontalDivider()

        ListItem(
            headlineContent = { Text(stringResource(R.string.settings_about_title)) },
            supportingContent = { 
                Text(stringResource(R.string.settings_about_desc)) 
            }
        )
    }
}
