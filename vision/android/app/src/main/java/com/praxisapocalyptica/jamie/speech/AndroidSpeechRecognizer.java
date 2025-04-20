package com/praxisapocalyptica/jamie.speech;

import android.content.Intent;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.os.Bundle;
import java.util.ArrayList;
import android.util.Log;
import android.content.Context; // Import Context

public class AndroidSpeechRecognizer implements RecognitionListener {

    private static final String TAG = "JamieSpeechRecognizer";
    private SpeechRecognizer speechRecognizer;
    private Intent recognizerIntent;
    private SpeechListener listener; // Custom interface to notify your app
    private Context context; // Store context to restart

    public interface SpeechListener {
        void onSpeechRecognized(String text);
        void onError(int error);
        void onListeningStarted(); // Added for feedback
        void onListeningStopped(); // Added for feedback
        // Add other methods for start/end of speech, etc.
    }

    public AndroidSpeechRecognizer(Context context, SpeechListener speechListener) {
        this.context = context;
        this.listener = speechListener;

        // Check if speech recognition is available
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            Log.e(TAG, "Speech Recognition not available on this device.");
            if (listener != null) listener.onError(SpeechRecognizer.ERROR_NOT_SUPPORTED);
            return;
        }

        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context);
        speechRecognizer.setRecognitionListener(this); // Set 'this' as the listener

        recognizerIntent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        recognizerIntent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        recognizerIntent.putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.getPackageName());
        recognizerIntent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false); // Set to true if you want partial results
        // recognizerIntent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US"); // Set language
        // recognizerIntent.putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true); // Prefer offline recognition if available

         Log.i(TAG, "SpeechRecognizer initialized.");
    }

    // Start listening (Call this after checking RECORD_AUDIO permission!)
    public void startListening() {
         if (speechRecognizer != null) {
             // Need to ensure RECORD_AUDIO permission is granted before calling startListening
             try {
                 speechRecognizer.startListening(recognizerIntent);
                 Log.i(TAG, "startListening called.");
                 if (listener != null) listener.onListeningStarted();
             } catch (SecurityException e) {
                 Log.e(TAG, "Missing RECORD_AUDIO permission!", e);
                 if (listener != null) listener.onError(SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS);
                 // Handle permission request in your Activity
             } catch (Exception e) {
                 Log.e(TAG, "Error calling startListening", e);
                 if (listener != null) listener.onError(SpeechRecognizer.ERROR_CLIENT);
             }
        } else {
             Log.e(TAG, "SpeechRecognizer is null.");
             if (listener != null) listener.onError(SpeechRecognizer.ERROR_INITIALIZATION_FAILURE);
        }
    }

    // Stop listening
    public void stopListening() {
        if (speechRecognizer != null) {
            speechRecognizer.stopListening();
            Log.i(TAG, "stopListening called.");
        }
    }

    // Cancel the current listening session (useful if you need to interrupt)
    public void cancelListening() {
         if (speechRecognizer != null) {
             speechRecognizer.cancel();
              Log.i(TAG, "cancelListening called.");
         }
    }

    // Clean up
    public void destroy() {
        if (speechRecognizer != null) {
            speechRecognizer.destroy();
            speechRecognizer = null;
            Log.i(TAG, "SpeechRecognizer destroyed.");
        }
    }

    // --- Implementation of RecognitionListener methods ---
    @Override
    public void onReadyForSpeech(Bundle params) { Log.d(TAG, "onReadyForSpeech"); }
    @Override
    public void onBeginningOfSpeech() { Log.d(TAG, "onBeginningOfSpeech"); }
    @Override
    public void onRmsChanged(float rmsdB) { /* Log.d(TAG, "onRmsChanged: " + rmsdB); */ } // Often too noisy to log
    @Override
    public void onBufferReceived(byte[] buffer) { Log.d(TAG, "onBufferReceived"); }
    @Override
    public void onEndOfSpeech() {
        Log.d(TAG, "onEndOfSpeech");
        if (listener != null) listener.onListeningStopped(); // Notify listener
    }

    @Override
    public void onError(int error) {
        Log.e(TAG, "onError: " + error + " - " + getErrorText(error)); // Log error code and meaning
        if (listener != null) listener.onError(error);

        // Decide whether to automatically restart listening based on the error
        switch (error) {
            case SpeechRecognizer.ERROR_AUDIO: // Audio recording error
            case SpeechRecognizer.ERROR_CLIENT: // Other client side errors
            case SpeechRecognizer.ERROR_SPEECH_TIMEOUT: // No speech detected
            case SpeechRecognizer.ERROR_NO_MATCH: // Speech detected but no result
            case SpeechRecognizer.ERROR_RECOGNIZER_BUSY: // Recognizer is busy
                // These errors often require restarting listening
                Log.i(TAG, "Attempting to restart listening...");
                startListening(); // Auto-restart
                break;
            case SpeechRecognizer.ERROR_NETWORK: // Network error
            case SpeechRecognizer.ERROR_NETWORK_TIMEOUT: // Network timeout
                // Network errors might need a delay or a different approach
                Log.w(TAG, "Network error, attempting restart after delay...");
                new android.os.Handler().postDelayed(this::startListening, 1000); // Restart after 1 second
                break;
            case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS: // Missing permission
            case SpeechRecognizer.ERROR_NOT_SUPPORTED: // Not supported
            case SpeechRecognizer.ERROR_BAD_PARAMS: // Invalid parameters
                // These errors usually indicate a configuration problem, don't auto-restart
                 Log.e(TAG, "Non-recoverable error, not auto-restarting.");
                break;
             case SpeechRecognizer.ERROR_SERVER: // Server error
                 Log.w(TAG, "Server error, attempting restart...");
                 startListening(); // Auto-restart
                 break;
            default:
                 Log.w(TAG, "Unknown error, attempting restart...");
                 startListening(); // Auto-restart for safety
                 break;
        }
    }

    @Override
    public void onResults(Bundle results) {
        Log.d(TAG, "onResults");
        ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        if (matches != null && !matches.isEmpty()) {
            String recognizedText = matches.get(0); // Get the most likely transcription
            Log.i(TAG, "Recognition result: " + recognizedText);
            if (listener != null) listener.onSpeechRecognized(recognizedText);
        } else {
             Log.i(TAG, "onResults: No match found.");
             // Optionally notify listener of no match if that's a distinct event you care about
             // if (listener != null) listener.onError(SpeechRecognizer.ERROR_NO_MATCH); // Or handle in onError
        }
        // startListening(); // Auto-restart happens in onError/onEndOfSpeech depending on flow
    }

    @Override
    public void onPartialResults(Bundle partialResults) {
         Log.d(TAG, "onPartialResults");
         // You can get intermediate results here if EXTRA_PARTIAL_RESULTS is true
         // ArrayList<String> matches = partialResults.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
         // if (matches != null && !matches.isEmpty()) {
         //     Log.i(TAG, "Partial result: " + matches.get(0));
         //     // You could update a UI element with partial text
         // }
    }

    @Override
    public void onEvent(int eventType, Bundle params) { Log.d(TAG, "onEvent: " + eventType); }


    // Helper method to get a human-readable string for error codes
    public static String getErrorText(int errorCode) {
        String message;
        switch (errorCode) {
            case SpeechRecognizer.ERROR_AUDIO: message = "Audio recording error"; break;
            case SpeechRecognizer.ERROR_CLIENT: message = "Client side error"; break;
            case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS: message = "Insufficient permissions"; break;
            case SpeechRecognizer.ERROR_NETWORK: message = "Network error"; break;
            case SpeechRecognizer.ERROR_NETWORK_TIMEOUT: message = "Network timeout"; break;
            case SpeechRecognizer.ERROR_NO_MATCH: message = "No match"; break;
            case SpeechRecognizer.ERROR_RECOGNIZER_BUSY: message = "Recognizer busy"; break;
            case SpeechRecognizer.ERROR_SERVER: message = "Error from server"; break;
            case SpeechRecognizer.ERROR_SPEECH_TIMEOUT: message = "No speech input"; break;
            case SpeechRecognizer.ERROR_TOO_MANY_REQUESTS: message = "Too many requests"; break; // Not in official docs but seen
            case SpeechRecognizer.ERROR_NOT_SUPPORTED: message = "Speech recognition not supported"; break;
            case SpeechRecognizer.ERROR_CANCELLED: message = "Recognition cancelled"; break;
            case SpeechRecognizer.ERROR_BAD_PARAMS: message = "Bad parameters"; break;
            default: message = "Unknown error code: " + errorCode; break;
        }
        return message;
    }
}
