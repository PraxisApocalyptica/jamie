import serial
import threading
import time
from typing import Callable, Optional

class ArduinoSerialCommunicator:
    """Manages serial communication with the Arduino (Motion controller)."""

    def __init__(self, port: str, baud_rate: int):
        self._port: str = port
        self._baud_rate: int = baud_rate
        self._serial_connection: Optional[serial.Serial] = None
        self._read_thread: Optional[threading.Thread] = None
        self._data_handler: Optional[Callable[[str], None]] = None
        self._stop_event = threading.Event() # Event to signal thread to stop

    @property
    def is_connected(self) -> bool:
        """Checks if the serial connection is currently open."""
        return self._serial_connection is not None and self._serial_connection.isOpen()

    def connect(self, data_handler: Callable[[str], None]) -> bool:
        """
        Establishes the serial connection and starts the read thread.

        Args:
            data_handler: A callback function to process received data strings.
        """
        if self.is_connected:
            print("Serial connection already open.")
            return True

        self._data_handler = data_handler
        try:
            # Add timeout to the serial connection to prevent blocking reads indefinitely
            self._serial_connection = serial.Serial(self._port, self._baud_rate, timeout=0.1)
            # Give Arduino time to reset after connection
            time.sleep(2)
            if self._serial_connection.isOpen():
                print(f"Serial connection established on {self._port} at {self._baud_rate}")
                # Clear any buffered data
                while self._serial_connection.in_waiting > 0:
                    print("Serial startup msg:", self._serial_connection.readline().decode('utf-8', errors='ignore').strip())

                # Start the background read thread
                self._stop_event.clear() # Ensure the stop event is clear
                self._read_thread = threading.Thread(target=self._read_serial_thread)
                self._read_thread.daemon = True # Allows main program to exit even if thread is running
                self._read_thread.start()

                return True
            else:
                print("Failed to open serial connection.")
                self._serial_connection = None # Ensure it's None if not open
                return False
        except serial.SerialException as e:
            print(f"Could not connect serial port {self._port}: {e}")
            self._serial_connection = None
            return False
        except Exception as e:
             print(f"An unexpected error occurred during serial connect: {e}")
             self._serial_connection = None
             return False


    def disconnect(self) -> None:
        """Closes the serial connection and stops the read thread."""
        print("Attempting to disconnect serial...")
        self._stop_event.set() # Signal the thread to stop
        if self._read_thread and self._read_thread.is_alive():
            self._read_thread.join(timeout=1.0) # Wait for the thread to finish (with timeout)
            if self._read_thread.is_alive():
                print("Warning: Read thread did not join cleanly.") # May need stronger thread termination depending on OS/serial library

        if self._serial_connection and self._serial_connection.isOpen():
            try:
                self._serial_connection.close()
                print("Serial connection closed.")
            except Exception as e:
                print(f"Error closing serial connection: {e}")
            finally:
                 self._serial_connection = None


    def _read_serial_thread(self) -> None:
        """Background thread function to read data from the serial port."""
        read_buffer = ""
        print("Serial read thread started.")
        # Read until stop event is set or connection is lost
        while not self._stop_event.is_set() and self.is_connected:
            try:
                # Read available bytes non-blocking (due to timeout=0.1)
                if self._serial_connection.in_waiting > 0:
                     byte = self._serial_connection.read(1) # Read one byte at a time
                     if byte:
                         char = byte.decode('utf-8', errors='ignore')
                         read_buffer += char
                         if char == '\n':
                             line = read_buffer.strip()
                             if line and self._data_handler:
                                 # Process the complete line using the handler callback
                                 # Note: Handler should not block or be very fast
                                 self._data_handler(line)
                             read_buffer = "" # Clear buffer
                 # If no data waiting, wait a brief moment to avoid busy-looping
                 # This sleep is important for resource usage
                time.sleep(0.005) # Small sleep

            except serial.SerialException as e:
                print(f"Serial read thread error: {e}")
                # Connection likely broken, signal disconnection
                self.disconnect() # Disconnect and stop thread
                break # Exit thread loop
            except Exception as e:
                print(f"An unexpected error in serial read thread: {e}")
                # Decide how to handle unexpected errors (e.g., try to disconnect/reconnect)
                time.sleep(0.1) # Wait before continuing loop


    def send_command(self, command: str) -> None:
        """
        Sends a command string to the Arduino. Appends newline if not present.

        Args:
            command: The command string to send.
        """
        if self.is_connected and self._serial_connection:
            try:
                # Ensure newline terminator
                if not command.endswith('\n'):
                    command += '\n'
                # Encode string to bytes and write
                self._serial_connection.write(command.encode('utf-8'))
                # print(f"Sent to Arduino: {command.strip()}") # Debugging

            except serial.SerialException as e:
                print(f"Error sending command '{command.strip()}': {e}")
                # Handle error (e.g., attempt reconnection)
            except Exception as e:
                print(f"An unexpected error sending command: {e}")
        else:
            print(f"Not connected to serial. Cannot send command: {command.strip()}")
