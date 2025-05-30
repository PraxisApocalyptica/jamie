from typing import Dict, Any

import yaml
import os
import logging


_logger = logging.getLogger(__name__)

def load_config(filepath: str = "config/jamie.yaml") -> Dict[str, Any]:
    """Loads configuration from a YAML file."""
    try:
        with open(filepath, 'r') as file:
            config = yaml.safe_load(file)
            _logger.debug(f"Configuration loaded from {os.path.abspath(filepath)}")
            # TODO: Add validation or default values if needed
            # Example: ensure 'motion' section exists
            if 'motion' not in config or 'serial_port' not in config['motion']:
                _logger.warning("Missing 'motion.serial_port' in config.")
                # Provide a default or raise error
            # Example: Ensure API key is present
            if 'api_keys' not in config or 'gemini' not in config['api_keys']:
                 _logger.warning("Missing 'api_keys.gemini' in config. Gemini API will not work.")
                 # Provide a placeholder or ensure client handles None key

            return config
    except FileNotFoundError:
        _logger.error(f"Error: Configuration file not found at {os.path.abspath(filepath)}")
        # Return an empty dict or raise an error, depending on desired behavior
        raise FileNotFoundError(f"Configuration file not found: {os.path.abspath(filepath)}")
    except yaml.YAMLError as e:
        _logger.error(f"Error parsing configuration file {os.path.abspath(filepath)}: {e}")
        # Return an empty dict or raise an error
        raise ValueError(f"Error parsing configuration file: {e}") from e
