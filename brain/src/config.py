import yaml
import os
from typing import Dict, Any

def load_config(filepath: str = "config/robot_config.yaml") -> Dict[str, Any]:
    """Loads configuration from a YAML file."""
    try:
        with open(filepath, 'r') as file:
            config = yaml.safe_load(file)
            print(f"Configuration loaded from {os.path.abspath(filepath)}")
            # TODO: Add validation or default values if needed
            # Example: ensure 'motion' section exists
            if 'motion' not in config or 'serial_port' not in config['motion']:
                print("Warning: Missing 'motion.serial_port' in config.")
                # Provide a default or raise error
            # Example: Ensure API key is present
            if 'api_keys' not in config or 'gemini' not in config['api_keys']:
                 print("Warning: Missing 'api_keys.gemini' in config. Gemini API will not work.")
                 # Provide a placeholder or ensure client handles None key

            return config
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {os.path.abspath(filepath)}")
        # Return an empty dict or raise an error, depending on desired behavior
        raise FileNotFoundError(f"Configuration file not found: {os.path.abspath(filepath)}")
    except yaml.YAMLError as e:
        print(f"Error parsing configuration file {os.path.abspath(filepath)}: {e}")
        # Return an empty dict or raise an error
        raise ValueError(f"Error parsing configuration file: {e}") from e

# Example of accessing config (in main.py or other modules)
# config = load_config()
# arduino_port = config['motion']['serial_port']
# gemini_key = config['api_keys']['gemini']
```

echo "brain/src/config.py created."

# brain/src/communication/__init__.py
echo "Creating brain/src/communication/__init__.py file..."
cat << 'EOF' > "$PROJECT_ROOT/brain/src/communication/__init__.py"
# This file makes 'communication' a Python package
# You might import key classes here for easier access
# from .arduino_serial import ArduinoSerialCommunicator
# from .phone_wifi_server import PhoneWifiServer
