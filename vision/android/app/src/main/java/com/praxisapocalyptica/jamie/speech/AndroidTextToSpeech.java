package com/praxisapocalyptica/jamie.speech;

import android.content.Context;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.util.Log;

import java.util.Locale;

public class AndroidTextToSpeech implements TextToSpeech.OnInitListener {

    private static final String TAG = "JamieTextToSpeech";
    private TextToSpeech textToSpeech;
    private boolean isInitialized = false;
    private Context context;

    // Callback for when TTS state changes (e.g., finished speaking)
    public interface TtsListener {
        void onTtsInitialized(boolean success);
        void onSpeechStart(String utteranceId);
        void onSpeechDone(String utteranceId);
        void onSpeechError(String utteranceId, String errorMessage);
    }

    private TtsListener listener;

    public AndroidTextToSpeech(Context context, TtsListener listener) {
        this.context = context;
        this.listener = listener;
        // Initialize the TTS engine. The OnInitListener will be called when ready.
        textToSpeech = new TextToSpeech(context, this);
        Log.i(TAG, "TextToSpeech initializing...");
    }

    @Override
    public void onInit(int status) {
        // Called when the TTS engine is initialized
        if (status == TextToSpeech.SUCCESS) {
            // Set language (check available languages on device)
            // Note: Language setting can fail if data is missing or locale is not supported
            int langResult = textToSpeech.setLanguage(Locale.US); // Example: US English

            if (langResult == TextToSpeech.LANG_MISSING_DATA || langResult == TextToSpeech.LANG_NOT_SUPPORTED) {
                Log.e(TAG, "TTS Language not supported or data missing.");
                isInitialized = false;
                 if (listener != null) listener.onTtsInitialized(false);
                // TODO: Prompt user to install language data or use a different language
            } else {
                isInitialized = true;
                Log.i(TAG, "TTS engine initialized successfully.");
                 if (listener != null) listener.onTtsInitialized(true);
                // Optional: Set speech rate, pitch, etc.
                // textToSpeech.setSpeechRate(1.0f);
                // textToSpeech.setPitch(1.0f);

                // Set a listener to know when speech starts/ends
                textToSpeech.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                    // Abstract methods you MUST implement
                    @Override public void onStart(String utteranceId) {
                        Log.d(TAG, "Speaking started: " + utteranceId);
                         if (listener != null) listener.onSpeechStart(utteranceId);
                    }
                    @Override public void onDone(String utteranceId) {
                        Log.d(TAG, "Speaking finished: " + utteranceId);
                         if (listener != null) listener.onSpeechDone(utteranceId);
                    }
                    @Override public void onError(String utteranceId) {
                         Log.e(TAG, "Speaking error: " + utteranceId);
                         if (listener != null) listener.onSpeechError(utteranceId, "Generic Error");
                    }

                    // Newer onError method (Android M and above)
                    @Override public void onError(String utteranceId, int errorCode) {
                        Log.e(TAG, "Speaking error: " + utteranceId + ", code: " + errorCode);
                         if (listener != null) listener.onSpeechError(utteranceId, "Error Code: " + errorCode);
                    }

                    // Optional overrides for progress/range (Android O and above)
                    // @Override public void onRangeStart(String utteranceId, int start, int end, int frame) {}
                    // @Override public void onAudioAvailable(String utteranceId, byte[] audio) {}
                });

                // If you had text waiting to be spoken, speak it now
                // speak("I am ready."); // Example greeting
            }
        } else {
            Log.e(TAG, "TTS engine initialization failed with status: " + status);
             if (listener != null) listener.onTtsInitialized(false);
        }
    }

    // Speak the given text
    public void speak(String text) {
        if (text == null || text.isEmpty()) return; // Don't speak empty text
        if (isInitialized && textToSpeech != null) {
            // Use QUEUE_FLUSH to stop current speech and start new one,
            // or QUEUE_ADD to add to the queue.
            // Use a unique UtteranceId to track specific speech outputs
            String utteranceId = "utteranceId_" + System.currentTimeMillis();
            textToSpeech.speak(text, TextToSpeech.QUEUE_FLUSH, null, utteranceId);
            Log.i(TAG, "Speaking: \"" + text + "\" with ID: " + utteranceId);
        } else {
            Log.e(TAG, "TTS engine not initialized. Cannot speak.");
            if (listener != null) listener.onSpeechError("N/A", "TTS not initialized");
        }
    }

    // Stop any ongoing speech
    public void stop() {
         if (textToSpeech != null) {
             textToSpeech.stop();
             Log.i(TAG, "TTS stop called.");
         }
    }

    // Clean up
    public void destroy() {
        stop(); // Stop any current speech first
        if (textToSpeech != null) {
            textToSpeech.shutdown(); // Release resources
            textToSpeech = null;
            Log.i(TAG, "TextToSpeech destroyed.");
        }
    }
}
