# src/protectors/file_protector.py

import os
import logging
from typing import Optional # Import Optional

# Import necessary modules from cryptography
# Need algorithms and modes from this import
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.exceptions import InvalidKey, InvalidTag
from cryptography.hazmat.backends import default_backend

# Assuming constants are accessible, potentially via an import or passed in
# from src.ai.clients.constants import GEMINI as GeminiConstants # Example import

class FileProtector:
    """
    Handles encryption and decryption of file data using AES-GCM
    with a key derived from a password and PBKDF2HMAC.
    """

    def __init__(self, password: str, constants) -> None:
        """
        Initializes the FileProtector.

        Args:
            password: The password to use for deriving the encryption key.
                      (WARNING: Should be securely managed, not hardcoded or from insecure source)
            constants: An object or dictionary containing necessary cryptographic constants
                       like KDF_SALT_SIZE, KDF_ITERATIONS, ENCRYPTION_ALGORITHM,
                       ENCRYPTION_MODE, AES_KEY_SIZE, IV_NONCE_SIZE.
                       ENCRYPTION_ALGORITHM and ENCRYPTION_MODE should be the actual
                       class objects (e.g., algorithms.AES, modes.GCM).
        """
        self._logger = logging.getLogger(self.__class__.__name__)

        if not password:
            raise ValueError("Password cannot be empty for FileProtector.")

        self._password = password.encode('utf-8') # Store encoded password bytes
        self._constants = constants

        # Validate constants presence and type (basic check)
        required_constants = {
            'KDF_SALT_SIZE': int,
            'KDF_ITERATIONS': int,
            'ENCRYPTION_ALGORITHM': type, # Expecting a class like algorithms.AES
            'ENCRYPTION_MODE': type,      # Expecting a class like modes.GCM
            'AES_KEY_SIZE': int,
            'IV_NONCE_SIZE': int
        }
        for const_name, const_type in required_constants.items():
             if not hasattr(self._constants, const_name):
                  raise ValueError(f"Missing required constant '{const_name}' in constants object.")
             if not isinstance(getattr(self._constants, const_name), const_type):
                  # More specific check for algorithm/mode classes
                  if const_name in ['ENCRYPTION_ALGORITHM', 'ENCRYPTION_MODE']:
                      if not (isinstance(getattr(self._constants, const_name), type) and
                              hasattr(getattr(self._constants, const_name), '__init__')): # Simple check for callable constructor
                           raise ValueError(f"Constant '{const_name}' is not a valid class type.")
                  else:
                    raise ValueError(f"Constant '{const_name}' should be of type {const_type}, but found {type(getattr(self._constants, const_name))}.")


        self._logger.debug("FileProtector initialized.")

    def _derive_key(self, salt: bytes) -> bytes:
        """Derives an encryption key from the password and salt using PBKDF2HMAC."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(), # Using SHA256 for PBKDF2
            length=self._constants.AES_KEY_SIZE, # Key length matches AES size
            salt=salt,
            iterations=self._constants.KDF_ITERATIONS,
            backend=default_backend()
        )
        # Use try-except for derive in case of password issues, though PBKDF2HMAC is usually robust
        try:
            return kdf.derive(self._password)
        except Exception as e:
             self._logger.error(f"Error during key derivation: {e}")
             raise # Re-raise the exception

    def encrypt(self, plaintext: bytes) -> bytes:
        """
        Encrypts bytes data using AES-GCM.

        Prepends salt and nonce to the ciphertext, appends the authentication tag.
        Returns salt || nonce || ciphertext || tag.

        Args:
            plaintext: The bytes data to encrypt.

        Returns:
            Encrypted bytes.

        Raises:
            ValueError: If constants or internal state are invalid.
            Exception: For unexpected encryption errors.
        """
        if not self._password:
             raise ValueError("FileProtector password not set.")
        if not self._constants:
             raise ValueError("FileProtector constants not set.")

        try:
            salt = os.urandom(self._constants.KDF_SALT_SIZE)
            key = self._derive_key(salt) # Derives key using password and generated salt

            nonce = os.urandom(self._constants.IV_NONCE_SIZE) # Generate unique nonce

            # ENCRYPTION_ALGORITHM and ENCRYPTION_MODE are expected to be classes
            cipher = Cipher(self._constants.ENCRYPTION_ALGORITHM(key), self._constants.ENCRYPTION_MODE(nonce), backend=default_backend())
            encryptor = cipher.encryptor()

            ciphertext = encryptor.update(plaintext) + encryptor.finalize()
            tag = encryptor.tag # Get the authentication tag

            # Combine salt, nonce, ciphertext, and tag for storage
            return salt + nonce + ciphertext + tag

        except Exception as e:
             self._logger.error(f"An unexpected error occurred during encryption: {e}", exc_info=True)
             raise # Re-raise the exception after logging

    def decrypt(self, encrypted_data: bytes) -> Optional[bytes]:
        """
        Decrypts bytes data using AES-GCM.

        Expects data in the format salt || nonce || ciphertext || tag.

        Args:
            encrypted_data: The bytes data to decrypt.

        Returns:
            Decrypted bytes or None if decryption fails (e.g., wrong password, corrupted data, InvalidTag).
        """
        if not self._password:
             self._logger.error("FileProtector password not set for decryption.")
             return None
        if not self._constants:
             self._logger.error("FileProtector constants not set for decryption.")
             return None

        salt_size = self._constants.KDF_SALT_SIZE
        nonce_size = self._constants.IV_NONCE_SIZE
        tag_size = 16 # GCM tag size is always 16 bytes (AES-GCM standard)

        # Minimum length = salt + nonce + tag + at least 1 byte of ciphertext
        min_len = salt_size + nonce_size + tag_size + 1

        if not encrypted_data or len(encrypted_data) < min_len:
             self._logger.error(f"Decryption failed: Encrypted data is empty or too short ({len(encrypted_data)} bytes). Expected at least {min_len}.")
             return None

        try:
            # Extract components from the encrypted data
            salt = encrypted_data[:salt_size]
            nonce = encrypted_data[salt_size : salt_size + nonce_size]
            tag_start_index = len(encrypted_data) - tag_size
            ciphertext = encrypted_data[salt_size + nonce_size : tag_start_index]
            tag = encrypted_data[tag_start_index:]

            # Derive the key using the password and the extracted salt
            key = self._derive_key(salt)

            # Initialize the cipher with the derived key, nonce, and tag (for GCM verification)
            cipher = Cipher(self._constants.ENCRYPTION_ALGORITHM(key), self._constants.ENCRYPTION_MODE(nonce, tag), backend=default_backend())
            decryptor = cipher.decryptor()

            # Decryption includes authentication check via the tag in the finalize step
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()

            return plaintext

        except InvalidTag:
            self._logger.error("Decryption failed: Authentication tag invalid. This usually means the password was incorrect or the encrypted data is corrupted.")
            return None
        except InvalidKey:
             self._logger.error("Decryption failed: Derived key invalid. This might indicate an issue with salt extraction or the key derivation process itself.")
             return None
        except Exception as e:
            self._logger.error(f"An unexpected error occurred during decryption: {e}", exc_info=True)
            return None
