package com/praxisapocalyptica/jamie.ui;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

// Import your components
import com/praxisapocalyptica/jamie.speech.AndroidSpeechRecognizer;
import com/praxisapocalyptica/jamie.speech.AndroidTextToSpeech;
import com/praxisapocalyptica/jamie.communication.BrainWifiCommunicator;
// Import perception components if using
// import com/praxisapocalyptica/jamie.perception.SlamManager;
// import com/praxisapocalyptica/jamie.perception.VisionProcessor;
// Import data structures you'll use (e.g., for objects, poses)
// import org.json.JSONObject; // If using org.json

public class MainActivity extends AppCompatActivity {

    private static final String TAG = "JamieMainActivity";
    private static final int PERMISSION_REQUEST_CODE = 100;

    // UI elements
    private TextView statusTextView;
    private Button startListeningButton;
    private Button connectPiButton; // Button to connect to Pi
    // Add other UI elements (e.g., camera preview, map visualization)

    // Robot components running on Android (Vision)
    private AndroidSpeechRecognizer speechRecognizer;
    private AndroidTextToSpeech textToSpeech;
    private BrainWifiCommunicator wifiCommunicator;
    // private SlamManager slamManager; // Handles ARCore/ARKit session
    // private VisionProcessor visionProcessor; // Runs ML models

    // --- Activity Lifecycle ---
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // TODO: Design your layout file (e.g., activity_main.xml)
        // setContentView(R.layout.activity_main);

        // TODO: Initialize UI elements based on your layout
        // statusTextView = findViewById(R.id.statusTextView);
        // startListeningButton = findViewById(R.id.startListeningButton);
        // connectPiButton = findViewById(R.id.connectPiButton);

        // Request necessary permissions at runtime
        checkAndRequestPermissions();

        // Initialize communication (Brain Wi-Fi Client)
        // Replace with your Raspberry Pi's IP address and port
        // Load these from preferences or a config file in a real app
        String piAddress = "YOUR_PI_IP_ADDRESS"; // <<<<< SET THIS >>>>>
        int piPort = 5000; // <<<<< SET THIS >>>>>

        wifiCommunicator = new BrainWifiCommunicator(piAddress, piPort, new BrainWifiCommunicator.CommunicationListener() {
            @Override
            public void onDataReceived(String data) {
                // Called when data is received from the Raspberry Pi (Brain)
                System.out.println("UI received data from Pi: " + data);
                android.util.Log.i(TAG, "Received data from Pi: " + data);

                // TODO: Parse received data (likely JSON from Pi)
                // Example: {"type": "speak", "text": "Hello from the robot brain"}
                // Or {"type": "status", "message": "Robot is navigating"}
                try {
                    // Example parsing using org.json.JSONObject (add dependency if needed)
                    // JSONObject jsonData = new JSONObject(data);
                    // String dataType = jsonData.optString("type"); // Use optString for safety

                    // if ("speak".equals(dataType)) {
                    //     String textToSpeak = jsonData.optString("text", ""); // Use optString with default
                    //     if (!textToSpeak.isEmpty()) {
                    //          textToSpeech.speak(textToSpeak);
                    //     }
                    // } else if ("status".equals(dataType)) {
                    //     String statusMessage = jsonData.optString("message", "Unknown Status");
                    //     updateStatusText("Status: " + statusMessage);
                    // } else if ("object_info".equals(dataType)) {
                    //     // Handle object info received from Pi (e.g., update UI display)
                    // }
                    // Add handling for other data types from Pi (e.g., map updates, object info)

                } catch (Exception e) { // Catch Exception if not using specific JSONException
                    System.err.println("Error parsing data from Pi: " + e.getMessage());
                    android.util.Log.e(TAG, "Error parsing data from Pi: " + e.getMessage());
                }
            }

            @Override
            public void onConnectionStatusChanged(boolean connected) {
                // Called when connection status changes
                updateStatusText("Brain Connected: " + connected);
                android.util.Log.i(TAG, "Brain Connected: " + connected);
                // Enable/disable UI elements based on connection status
                // startListeningButton.setEnabled(connected); // Example
            }

            @Override
            public void onError(String errorMessage) {
                // Called on communication errors
                System.err.println("Brain Comm Error: " + errorMessage);
                android.util.Log.e(TAG, "Brain Comm Error: " + errorMessage);
                updateStatusText("Comm Error: " + errorMessage);
                // TODO: Implement reconnection logic or user notification
            }
        });


        // Initialize Speech Recognition
        speechRecognizer = new AndroidSpeechRecognizer(this, new AndroidSpeechRecognizer.SpeechListener() {
            @Override public void onSpeechRecognized(String text) {
                System.out.println("Recognized Speech: " + text);
                android.util.Log.i(TAG, "Recognized Speech: " + text);
                updateStatusText("Heard: " + text);
                // TODO: Send the recognized text command to the Brain (Raspberry Pi)
                // Example: Send as JSON { "type": "command", "text": text }
                // Use a JSON library (org.json or Gson)
                // try {
                //    JSONObject commandJson = new JSONObject();
                //    commandJson.put("type", "command");
                //    commandJson.put("text", text);
                //    wifiCommunicator.sendData(commandJson.toString());
                // } catch (JSONException e) {
                //     System.err.println("Error creating command JSON: " + e.getMessage());
                // }

                // Speech recognizer often stops after processing, need to restart listening in onError/onEndOfSpeech
            }

            @Override public void onError(int error) {
                System.err.println("ASR Error: " + error);
                android.util.Log.e(TAG, "ASR Error: " + error);
                updateStatusText("Speech Error: " + AndroidSpeechRecognizer.getErrorText(error));
                // Auto-restart logic is handled inside AndroidSpeechRecognizer
            }

            @Override public void onListeningStarted() {
                updateStatusText("Listening...");
                android.util.Log.i(TAG, "Listening started.");
                // Update UI (e.g., change button color/text)
            }

            @Override public void onListeningStopped() {
                updateStatusText("Tap to listen"); // Or previous status
                android.util.Log.i(TAG, "Listening stopped.");
                 // Update UI
            }
            // Implement other listener methods as needed
        });

        // Initialize Text-to-Speech
        textToSpeech = new AndroidTextToSpeech(this, new AndroidTextToSpeech.TtsListener() {
             @Override public void onTtsInitialized(boolean success) {
                 updateStatusText("TTS Ready: " + success);
                 android.util.Log.i(TAG, "TTS Ready: " + success);
                  // You can speak an initial greeting here if needed
                  // if(success) textToSpeech.speak("Hello");
             }
             @Override public void onSpeechStart(String utteranceId) {
                 updateStatusText("Speaking...");
                 android.util.Log.i(TAG, "Speaking started: " + utteranceId);
             }
             @Override public void onSpeechDone(String utteranceId) {
                 updateStatusText("Finished speaking."); // Or previous status
                 android.util.Log.i(TAG, "Speaking finished: " + utteranceId);
                 // TODO: Notify Brain (Pi) that speaking is done if needed for dialogue flow
                 // Example: wifiCommunicator.sendData("{\"type\": \"speech_response_done\", \"utterance_id\": \"" + utteranceId + "\"}");
             }
             @Override public void onSpeechError(String utteranceId, String errorMessage) {
                  System.err.println("TTS Speaking Error: " + errorMessage);
                  android.util.Log.e(TAG, "Speaking Error: " + utteranceId + " - " + errorMessage);
                  updateStatusText("Speaking Error!");
             }
        });


        // TODO: Initialize Vision/SLAM components (requires CAMERA permission)
        // Check ARCore availability/compatibility before initializing SlamManager
        // slamManager = new SlamManager(this, new SlamManager.FrameListener() { ... });
        // visionProcessor = new VisionProcessor(this, new VisionProcessor.VisionListener() { ... });


        // --- Setup UI Listeners ---
        // TODO: Connect listeners to your actual buttons/views in the layout
        /*
        startListeningButton.setOnClickListener(v -> {
             if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                 speechRecognizer.startListening(); // Start listening via microphone
             } else {
                 updateStatusText("Require Audio Permission");
                 checkAndRequestPermissions(); // Ask for permission again
             }
        });

        connectPiButton.setOnClickListener(v -> {
             if (!wifiCommunicator.is_connected()) {
                 updateStatusText("Connecting to Brain...");
                 wifiCommunicator.connect(); // Connect on button click
             } else {
                 updateStatusText("Already connected to Brain.");
                 // Optionally disconnect if already connected
                 // wifiCommunicator.disconnect();
             }
        });
        */

        // TODO: Setup other UI listeners (e.g., for camera preview touches, map interactions)
    }

    // --- Runtime Permissions ---
    private void checkAndRequestPermissions() {
        String[] permissions = {
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.CAMERA, // For ARCore/Camera Feed
            // Add other necessary permissions like WRITE_EXTERNAL_STORAGE if needed
        };
        boolean permissionsGranted = true;
        for (String permission : permissions) {
            if (ContextCompat.checkSelfPermission(this, permission) != PackageManager.PERMISSION_GRANTED) {
                permissionsGranted = false;
                break;
            }
        }

        if (!permissionsGranted) {
            ActivityCompat.requestPermissions(this, permissions, PERMISSION_REQUEST_CODE);
        } else {
            // Permissions are already granted, proceed with initialization that requires them
            // Example: You might start the camera feed or AR session here
            // updateStatusText("Permissions granted.");
            // initVisionAndSlam(); // Call a method to initialize vision/SLAM
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == PERMISSION_REQUEST_CODE) {
            boolean allGranted = true;
            for (int result : grantResults) {
                if (result != PackageManager.PERMISSION_GRANTED) {
                    allGranted = false;
                    break;
                }
            }
            if (allGranted) {
                updateStatusText("All permissions granted.");
                // Permissions granted, proceed with initialization that requires them
                // initVisionAndSlam(); // Call a method to initialize vision/SLAM
                // speechRecognizer.startListening(); // Start listening if desired on permission granted
            } else {
                updateStatusText("Permissions not granted.");
                Toast.makeText(this, "Permissions required for full functionality", Toast.LENGTH_LONG).show();
            }
        }
    }

    // --- Method to initialize Vision and SLAM (call after permissions granted) ---
    /*
    private void initVisionAndSlam() {
        if (slamManager == null) { // Check if not already initialized
            slamManager = new SlamManager(this, new SlamManager.FrameListener() {
                 @Override public void onNewFrame(Frame frame, Pose robotPose) {
                     // Called when ARCore provides a new frame
                     // TODO: Pass frame to VisionProcessor for object detection
                     // visionProcessor.processFrame(frame, robotPose);
                     // TODO: Send robotPose (phone's pose) to Brain via Wi-Fi
                     // wifiCommunicator.sendData(formatPoseToJson(robotPose)); // Need to implement formatPoseToJson
                 }
                 @Override public void onTrackingStateChanged(TrackingState state) { updateStatusText("AR Tracking: " + state); }
                 @Override public void onError(String message) { updateStatusText("AR Error: " + message); }
            });
        }
        if (visionProcessor == null) { // Check if not already initialized
            visionProcessor = new VisionProcessor(this, new VisionProcessor.VisionListener() {
                 @Override public void onObjectsDetected(List<DetectedObject> objects, Bitmap frameBitmap, Pose cameraPose) {
                     // Called when vision processing detects objects
                     System.out.println("Detected " + objects.size() + " objects.");
                     android.util.Log.i(TAG, "Detected " + objects.size() + " objects.");
                     // TODO: Send the detected objects list (including 3D pose/masks) to the Brain (Pi) via Wi-Fi
                     // wifiCommunicator.sendData(formatDetectedObjectsToJson(objects)); // Need to implement this helper
                 }
                 @Override public void onError(String message) {
                     System.err.println("Vision Error: " + message);
                     android.util.Log.e(TAG, "Vision Error: " + message);
                     updateStatusText("Vision Error!");
                 }
            });
        }

        // TODO: Start Camera Preview and AR Session
        // This often involves setting up a GLSurfaceView or ARCore's ARSceneView
        // slamManager.resumeArSession(); // Starts/Resumes ARCore session
    }
    */


    // --- Helper to Update Status Text (safe from background threads) ---
    private void updateStatusText(String message) {
        // Use runOnUiThread to ensure UI updates happen on the main thread
        runOnUiThread(() -> {
            if (statusTextView != null) {
                statusTextView.setText(message);
            } else {
                System.out.println("Status (UI not ready): " + message); // Fallback logging
            }
        });
    }


    // --- Activity Lifecycle Cleanup ---
    @Override
    protected void onResume() {
        super.onResume();
        // TODO: Resume camera/AR session
        // if (slamManager != null) slamManager.resumeArSession();
        // if (visionProcessor != null) visionProcessor.resumeCamera(); // If it manages camera separately
        // if (speechRecognizer != null && ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
        //     speechRecognizer.startListening(); // If listening should resume automatically
        // }
    }

    @Override
    protected void onPause() {
        super.onPause();
        // TODO: Pause camera/AR session
        // if (slamManager != null) slamManager.pauseArSession();
        // if (visionProcessor != null) visionProcessor.pauseCamera(); // If it manages camera separately
        // if (speechRecognizer != null) speechRecognizer.stopListening(); // If listening should stop when paused
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        // Clean up components
        if (speechRecognizer != null) speechRecognizer.destroy();
        if (textToSpeech != null) textToSpeech.destroy();
        if (wifiCommunicator != null) wifiCommunicator.disconnect();
        // TODO: Destroy other components (SLAM, Vision Processor, ExecutorService for comms)
        // if (slamManager != null) slamManager.destroyArSession();
        // if (visionProcessor != null) visionProcessor.destroy();
        if (wifiCommunicator != null) wifiCommunicator.shutdownExecutor(); // Shutdown the thread pool
    }

    // --- Helper methods for JSON formatting (You need a JSON library like org.json or Gson) ---
    /*
    private String formatPoseToJson(Pose pose) {
        // Example using org.json.JSONObject
        try {
            JSONObject json = new JSONObject();
            json.put("type", "slam_update");
            JSONObject poseJson = new JSONObject();
            poseJson.put("x", pose.tx());
            poseJson.put("y", pose.ty());
            poseJson.put("z", pose.tz());
            poseJson.put("qx", pose.qx());
            poseJson.put("qy", pose.qy());
            poseJson.put("qz", pose.qz());
            poseJson.put("qw", pose.qw());
            json.put("pose", poseJson);
            // TODO: Add map data if available/needed
            return json.toString();
        } catch (JSONException e) {
            System.err.println("Error formatting pose JSON: " + e.getMessage());
            return null;
        }
    }

    private String formatDetectedObjectsToJson(List<DetectedObject> objects) {
        // Example using org.json.JSONObject and JSONArray
        try {
            JSONObject json = new JSONObject();
            json.put("type", "vision_update");
            JSONArray objectsArray = new JSONArray();
            for (DetectedObject obj : objects) {
                JSONObject objJson = new JSONObject();
                objJson.put("class", obj.objectClass);
                objJson.put("confidence", obj.confidence);
                // Add bounding box
                // Add mask (depends on how you represent it)
                // Add 3D pose if available
                 if (obj.poseX != 0 || obj.poseY != 0 || obj.poseZ != 0 || obj.poseQx != 0 || obj.poseQy != 0 || obj.poseQz != 0 || obj.poseQw != 0) { // Simple check if pose is set
                      JSONObject poseJson = new JSONObject();
                      poseJson.put("x", obj.poseX);
                      poseJson.put("y", obj.poseY);
                      poseJson.put("z", obj.poseZ);
                      poseJson.put("qx", obj.poseQx);
                      poseJson.put("qy", obj.poseQy);
                      poseJson.put("qz", obj.qz);
                      poseJson.put("qw", obj.qw);
                      objJson.put("pose", poseJson);
                 }

                objectsArray.put(objJson);
            }
            json.put("objects", objectsArray);
            return json.toString();
        } catch (JSONException e) {
             System.err.println("Error formatting objects JSON: " + e.getMessage());
             return null;
        }
    }
    */
}
