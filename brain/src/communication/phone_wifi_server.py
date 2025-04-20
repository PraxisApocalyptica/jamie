import socket
import threading
import json
import time
from typing import Callable, Optional, Dict, Any

class PhoneWifiServer:
    """Manages a Wi-Fi server to receive data (JSON) from the Android (Vision) app."""

    def __init__(self, host: str, port: int, data_handler: Callable[[Dict[str, Any]], None]):
        self._host: str = host
        self._port: int = port
        self._data_handler: Callable[[Dict[str, Any]], None] = data_handler
        self._server_socket: Optional[socket.socket] = None
        self._listen_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._client_socket: Optional[socket.socket] = None # Only expecting one client (the phone)
        self._client_address: Optional[tuple] = None
        self._client_read_thread: Optional[threading.Thread] = None

    @property
    def is_listening(self) -> bool:
        """Checks if the server socket is open and listening."""
        return self._server_socket is not None

    @property
    def is_client_connected(self) -> bool:
        """Checks if a client (phone) is currently connected."""
        # More robust check than _closed
        return self._client_socket is not None and self._client_socket.fileno() != -1


    def start(self, data_handler: Optional[Callable[[Dict[str, Any]], None]] = None) -> bool:
        """Starts the Wi-Fi server listening thread."""
        if self.is_listening:
            print("Wi-Fi server is already listening.")
            return True

        # Allow updating the data handler during start if needed, otherwise use the one from init
        if data_handler:
            self._data_handler = data_handler

        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Allow reusing the address in case of recent disconnect
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind((self._host, self._port))
            self._server_socket.listen(1) # Listen for maximum 1 client (the phone)
            print(f"Wi-Fi server listening on {self._host}:{self._port}")

            self._stop_event.clear()
            self._listen_thread = threading.Thread(target=self._listen_for_clients_thread)
            self._listen_thread.daemon = True # Allows main program to exit
            self._listen_thread.start()

            return True
        except Exception as e:
            print(f"Error starting Wi-Fi server: {e}")
            self._server_socket = None
            return False

    def stop(self) -> None:
        """Stops the Wi-Fi server and disconnects any connected client."""
        print("Attempting to stop Wi-Fi server...")
        self._stop_event.set() # Signal threads to stop
        self.disconnect_client() # Disconnect any currently connected client

        if self._server_socket:
            try:
                # Unblock the accept call by connecting to self
                socket.create_connection((self._host, self._port), timeout=0.1).close()
            except Exception:
                pass # Ignore errors during self-connect

            try:
                self._server_socket.close()
                print("Wi-Fi server socket closed.")
            except Exception as e:
                print(f"Error closing server socket: {e}")
            finally:
                self._server_socket = None

        if self._listen_thread and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=1.0)
            if self._listen_thread.is_alive():
                print("Warning: Listen thread did not join cleanly.")


    def _listen_for_clients_thread(self) -> None:
        """Background thread to accept client connections."""
        print("Wi-Fi listen thread started.")
        self._server_socket.settimeout(1.0) # Set a timeout so accept is not blocking forever

        while not self._stop_event.is_set():
            try:
                # Accept a new connection
                client_socket, client_address = self._server_socket.accept()
                print(f"Client connected from {client_address}")

                # Disconnect previous client if any (only expecting one)
                self.disconnect_client()

                self._client_socket = client_socket
                self._client_address = client_address

                # Start a new thread to read from this client
                self._client_read_thread = threading.Thread(target=self._read_client_data_thread)
                self._client_read_thread.daemon = True # Allows main program to exit
                self._client_read_thread.start()

            except socket.timeout:
                # Timeout occurred, check stop_event and continue listening
                pass
            except Exception as e:
                # Handle other potential errors during accept (e.g., server socket closed)
                if not self._stop_event.is_set():
                    print(f"Error accepting client connection: {e}")
                time.sleep(0.1) # Wait before trying again (prevents busy loop if error is persistent)

        print("Wi-Fi listen thread stopped.")


    def _read_client_data_thread(self) -> None:
        """Background thread to read data from a connected client (phone)."""
        print(f"Client read thread started for {self._client_address}")
        client_socket = self._client_socket # Use the current client socket
        if client_socket is None:
            print("Error: Read thread started without a valid client socket.")
            return

        # Use a file-like object for easier reading of lines
        # Wrap in a try-finally to ensure socket is handled on exit
        try:
            # Set a read timeout so readline is not blocking indefinitely
            client_socket.settimeout(1.0)
            with client_socket.makefile('r') as client_file:
                # Read until stop event is set or socket is no longer connected
                while not self._stop_event.is_set() and self.is_client_connected:
                    try:
                        # Read a line from the socket (blocks up to timeout)
                        line = client_file.readline()
                        if not line: # readline returns empty string if socket is closed
                            print(f"Client {self._client_address} disconnected.")
                            break # Exit loop if client disconnects

                        line = line.strip()
                        if line:
                            # Assume data is JSON, parse it
                            try:
                                data = json.loads(line)
                                # Process the received JSON data using the handler callback
                                # Note: Handler should not block or be very fast
                                if self._data_handler:
                                    # Execute handler in the main loop's context or another thread pool
                                    # if it might be slow or interact with non-thread-safe components.
                                    # For simplicity here, calling directly.
                                    self._data_handler(data)
                            except json.JSONDecodeError:
                                print(f"Received invalid JSON from {self._client_address}: {line}")
                            except Exception as e:
                                print(f"Error processing received data from {self._client_address}: {e}")

                    except socket.timeout:
                        # Timeout occurred, check stop_event and continue reading
                        pass # Expected if no data for a while
                    except Exception as e:
                         # Handle other potential errors during reading
                         if self.is_client_connected: # Report error only if connection was active
                             print(f"Error reading from client {self._client_address}: {e}")
                         break # Exit loop on read error

        finally:
            # Ensure client is disconnected if we exit the loop
            self.disconnect_client()
            print(f"Client read thread stopped for {self._client_address}.")


    def disconnect_client(self) -> None:
        """Disconnects the currently connected client."""
        if self._client_socket and self.is_client_connected:
            print(f"Disconnecting client {self._client_address}...")
            try:
                # Attempt graceful shutdown
                self._client_socket.shutdown(socket.SHUT_RDWR)
                self._client_socket.close()
            except Exception as e:
                print(f"Error closing client socket: {e}")
            finally:
                self._client_socket = None # Clear client socket reference
                self._client_address = None
                # The client read thread should exit after the socket is closed

    def send_data_to_client(self, data: Dict[str, Any]) -> None:
        """Sends JSON data to the connected client (phone)."""
        if self.is_client_connected and self._client_socket:
            try:
                message = json.dumps(data) + '\n' # Send JSON string terminated by newline
                self._client_socket.sendall(message.encode('utf-8'))
                # print(f"Sent to client {self._client_address}: {message.strip()}") # Debugging
            except Exception as e:
                print(f"Error sending data to client {self._client_address}: {e}")
                # Assume connection lost on send error
                self.disconnect_client()


# --- Example Usage (in main.py) ---
# # Inside JamieRobot.__init__
# # Assume config has ['vision']['wifi_host'] and ['vision']['wifi_port']
# # self.vision_comm = PhoneWifiServer(
# #    host=self.config['vision']['wifi_host'],
# #    port=self.config['vision']['wifi_port'],
# #    # Data handler registered in .start()
# # )

# # # Inside JamieRobot.run
# # # Register the handler here during start
# # self.vision_comm.start(data_handler=self._handle_vision_data)
# # # Data reception is handled by _handle_vision_data callback
# # # To send data to phone (e.g., text for TTS):
# # # self.vision_comm.send_data_to_client({"type": "speak", "text": "Hello from Jamie"})
# # # In cleanup:
# # self.vision_comm.stop()
