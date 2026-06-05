package app.walkpedia

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.util.Locale

/** On-device TTS via android.speech.tts.TextToSpeech. */
class SpeechManager(context: Context, private val onFinish: () -> Unit) {
    private var ready = false
    private val tts = TextToSpeech(context) { status ->
        if (status == TextToSpeech.SUCCESS) {
            ready = true
        }
    }.apply {
        language = Locale.US
        setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) {}
            override fun onDone(utteranceId: String?) { onFinish() }
            @Deprecated("deprecated in API 21")
            override fun onError(utteranceId: String?) { onFinish() }
        })
    }

    var isSpeaking = false
        private set

    fun speak(text: String, id: String) {
        if (!ready) return
        isSpeaking = true
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, id)
    }

    fun stop() {
        tts.stop()
        isSpeaking = false
    }

    fun shutdown() = tts.shutdown()
}
