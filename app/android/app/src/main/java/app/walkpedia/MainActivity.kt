package app.walkpedia

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat

class MainActivity : ComponentActivity() {
    private lateinit var db: WalkPediaDatabase
    private lateinit var speech: SpeechManager
    private lateinit var controller: PlaybackController
    private lateinit var location: LocationProvider

    private val nowPlaying = mutableStateOf<Article?>(null)
    private val queue = mutableStateOf<List<Article>>(emptyList())

    private val permLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted -> if (granted) location.start() }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        db = WalkPediaDatabase.open(this)
        speech = SpeechManager(this) { runOnUiThread { controller.advance() } }
        controller = PlaybackController(db, speech) { np, q ->
            runOnUiThread { nowPlaying.value = np; queue.value = q }
        }
        location = LocationProvider(this) { controller.updateLocation(it) }

        setContent {
            WalkPediaScreen(nowPlaying.value, queue.value, controller.radiusMeters) {
                controller.skip()
            }
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
            == PackageManager.PERMISSION_GRANTED
        ) {
            location.start()
        } else {
            permLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        location.stop()
        speech.shutdown()
    }
}

@Composable
fun WalkPediaScreen(
    nowPlaying: Article?,
    queue: List<Article>,
    radius: Double,
    onSkip: () -> Unit
) {
    MaterialTheme {
        Column(
            Modifier.fillMaxSize().padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Text("WalkPedia", style = MaterialTheme.typography.headlineMedium)

            if (nowPlaying != null) {
                Card {
                    Column(Modifier.padding(16.dp)) {
                        Text("🔊 ${nowPlaying.title}", style = MaterialTheme.typography.titleMedium)
                        Text(
                            nowPlaying.summary,
                            style = MaterialTheme.typography.bodyMedium,
                            maxLines = 8
                        )
                    }
                }
            } else {
                Text(
                    "No article within ${radius.toInt()} m",
                    color = MaterialTheme.colorScheme.outline
                )
            }

            if (queue.isNotEmpty()) {
                Text("Up next", style = MaterialTheme.typography.titleSmall)
                LazyColumn(Modifier.weight(1f)) {
                    items(queue) { Text("• ${it.title}") }
                }
            } else {
                Spacer(Modifier.weight(1f))
            }

            Button(onClick = onSkip, enabled = nowPlaying != null) { Text("Skip") }
        }
    }
}
