package com/praxisapocalyptica/jamie.communication;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.net.Socket;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

// Import JSON libraries if needed (e.g., org.json or com.google.gson)
// import org.json.JSONObject;
// import org.json.JSONException;
// import com.google.gson.Gson; // Recommended if using Gson

public class BrainWifiCommunicator {

    private String piAddress;
    private int piPort;
    private Socket socket;
    private PrintWriter out;
    private BufferedReader in;
    private boolean isConnected = false;
    private CommunicationListener listener;

    // Using an ExecutorService to manage background threads
    private ExecutorService executorService;

    public interface CommunicationListener {
        void onDataReceived(String data); // Or better: onJsonDataReceived(JSONObject data) if always JSON
        void onConnectionStatusChanged(boolean connected);
        void onError(String errorMessage);
    }

    public BrainWifiCommunicator(String piAddress, int piPort, CommunicationListener listener) {
        this.piAddress = piAddress;
        this.piPort = piPort;
        this.listener = listener;
        // Create a fixed-size thread pool for communication tasks
        executorService = Executors.newFixedThreadPool(2); // One for connecting/sending, one for receiving
    }

    public boolean is_connected() { // Renamed from is_connected to follow Java conventions
        return isConnected && (socket != null && !socket.isClosed());
    }

    // Connect to the Raspberry Pi server (Call this from UI/Service logic)
    public void connect() {
        if (is_connected()) {
            System.out.println("Already connected to Brain.");
            return;
        }
        // Submit the connection task to the executor service
        executorService.submit(this::runConnection);
    }

    private void runConnection() {
        try {
            System.out.println("Attempting to connect to Brain at " + piAddress + ":" + piPort);
            socket = new Socket(piAddress, piPort);
            out = new PrintWriter(socket.getOutputStream(), true); // AutoFlush
            in = new BufferedReader(new InputStreamReader(socket.getInputStream()));
            isConnected = true;
            if (listener != null) listener.onConnectionStatusChanged(true);
            System.out.println("Connected to Brain.");

            // Start the receiving task after successful connection
            executorService.submit(this::receiveData);

        } catch (IOException e) {
            isConnected = false;
            if (listener != null) listener.onConnectionStatusChanged(false);
            if (listener != null) listener.onError("Connection failed: " + e.getMessage());
            System.err.println("Connection to Brain failed: " + e.getMessage());
            // TODO: Implement reconnection logic here or in the calling code
        }
    }


    // Task method to receive data continuously
    private void receiveData() {
        System.out.println("Brain data receive thread started.");
        try {
            String line;
            // Read lines terminated by newline while connected
            while (isConnected() && in != null && (line = in.readLine()) != null) { // Check if in is not null
                System.out.println("Received from Brain: " + line);
                // Process the received data string (assumed to be a JSON string)
                if (listener != null) {
                     // TODO: Add JSON parsing here if always expecting JSON
                     // try {
                     //     JSONObject jsonData = new JSONObject(line);
                     //     listener.onJsonDataReceived(jsonData); // If listener has this method
                     // } catch (JSONException e) {
                     //     System.err.println("Received non-JSON data or invalid JSON: " + line);
                     //     listener.onDataReceived(line); // Pass raw string if parsing fails
                     // }
                     listener.onDataReceived(line); // Pass raw string
                }
            }
        } catch (IOException e) {
             if (isConnected()) { // Only report error if connection was supposedly active
                 if (listener != null) listener.onError("Receive error: " + e.getMessage());
                 System.err.println("Receive error from Brain: " + e.getMessage());
             }
        } finally {
            // Ensure disconnection on error or stream end
            disconnect();
        }
        System.out.println("Brain data receive thread stopped.");
    }


    // Send a command string (assumed to be a JSON string) to the Raspberry Pi
    public void sendData(String data) {
         if (!is_connected()) {
             System.err.println("Not connected to Brain. Cannot send data: " + data);
             if (listener != null) listener.onError("Send error: Not connected.");
             return;
         }
         if (out == null) {
              System.err.println("Output stream is null. Cannot send data: " + data);
              if (listener != null) listener.onError("Send error: Output stream null.");
              disconnect(); // Treat as a connection issue
              return;
         }

        // Submit the sending task to the executor service
        executorService.submit(() -> { // Use lambda for simple task
            try {
                // Ensure newline terminator
                if (!data.endsWith("\n")) {
                    data += "\n";
                }
                out.println(data); // Send the string followed by a newline
                System.out.println("Sent to Brain: " + data.trim()); // Trim for logging

            } catch (Exception e) {
                if (listener != null) listener.onError("Send error: " + e.getMessage());
                System.err.println("Error sending to Brain: " + e.getMessage());
                // Assume connection lost on send error
                disconnect();
            }
        });
    }

    // Disconnect
    public void disconnect() {
        boolean wasConnected = isConnected(); // Check state before setting flag
        isConnected = false; // Set flag first

        try {
            if (socket != null && !socket.isClosed()) {
                // Attempt graceful shutdown first
                 try {
                    socket.shutdownInput();
                    socket.shutdownOutput();
                 } catch (IOException e) {
                     // Ignore error if streams are already closed
                 }
                socket.close();
                System.out.println("Disconnected from Brain.");
            }
        } catch (IOException e) {
            System.err.println("Error closing socket: " + e.getMessage());
        } finally {
            socket = null;
            out = null;
            in = null;
             if (wasConnected) { // Only report disconnection if it was active
                if (listener != null) listener.onConnectionStatusChanged(false);
             }
            // ExecutorService should ideally be shut down when the application exits (in onDestroy)
        }
    }

    // Shutdown the executor service when the app/component is destroyed
    public void shutdownExecutor() {
        if (executorService != null && !executorService.isShutdown()) {
            executorService.shutdownNow(); // Attempt to stop all tasks immediately
            System.out.println("Executor service shut down.");
        }
    }
}
