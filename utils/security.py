from cryptography.fernet import Fernet, InvalidToken # Import InvalidToken
import os
import logging
logger = logging.getLogger("VisionAlign.Security") # More specific logger name

class SecurityManager:
    def __init__(self, key_file: str = "security.key"):

        self.key_file = key_file
        self.key = self._load_or_create_key()
        if self.key:
            # <<< DEBUG: Log first few bytes of the key >>>
            logger.debug(f"Loaded/Generated Key (first 10 bytes): {self.key[:10]!r}")
            try:
                self.cipher_suite = Fernet(self.key)
                logger.info(f"SecurityManager initialized successfully using key file: {self.key_file}")
            except ValueError as e:
                logger.error(f"Invalid key format in {self.key_file}: {e}")
                # Handle invalid key scenario - maybe raise an exception or exit
                raise ValueError(f"Invalid key format in {self.key_file}") from e
        else:
            # Handle case where key couldn't be loaded/created
            logger.error(f"Failed to load or create security key at {self.key_file}.")
            raise RuntimeError(f"Failed to load or create security key at {self.key_file}")


    def _load_or_create_key(self) -> bytes | None:
        """
        Loads the encryption key from the specified file or creates a new one if not found.

        Returns:
            bytes | None: The encryption key, or None if an error occurred.
        """
        try:
            # Ensure the directory exists if key_file includes a path
            key_dir = os.path.dirname(self.key_file)
            if key_dir and not os.path.exists(key_dir):
                 logger.info(f"Creating directory for key file: {key_dir}")
                 os.makedirs(key_dir, exist_ok=True) # Create directory if needed

            if os.path.exists(self.key_file):
                logger.info(f"Loading existing key from {self.key_file}")
                with open(self.key_file, "rb") as f:
                    key = f.read()
                    # Basic validation: Fernet keys are base64 encoded and have a specific length range
                    if not key or len(key) < 44: # Fernet keys are base64 of 32 bytes = 44 chars
                         logger.error(f"Key file {self.key_file} seems corrupted or empty.")
                         return None
                    return key
            else:
                logger.warning(f"Key file {self.key_file} not found. Generating a new key.")
                key = Fernet.generate_key()
                with open(self.key_file, "wb") as f:
                    f.write(key)
                # IMPORTANT: Set appropriate file permissions for security
                try:
                    os.chmod(self.key_file, 0o600) # Read/Write for owner only (Unix-like systems)
                    logger.info(f"Set permissions for {self.key_file} to 600.")
                except OSError:
                     # This might fail on Windows or if permissions are restricted
                     logger.warning(f"Could not set restrictive permissions on {self.key_file}. "
                                    "Ensure the key file is adequately protected by filesystem ACLs.")
                except AttributeError:
                     # os.chmod might not be available on all OS (though common)
                     logger.warning(f"os.chmod not available on this system. "
                                    "Ensure the key file {self.key_file} is adequately protected.")
                logger.info(f"New key generated and saved to {self.key_file}")
                return key
        except IOError as e:
            logger.error(f"Error accessing key file {self.key_file}: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during key handling: {e}")
            return None

    def encrypt_data(self, data: bytes) -> bytes:
        if not isinstance(data, bytes):
             raise TypeError("Data to encrypt must be bytes.")
        if not hasattr(self, 'cipher_suite'):
             logger.error("Encryption attempted before SecurityManager was properly initialized.")
             raise RuntimeError("Cipher suite not available. Check key loading/generation.")
        logger.debug(f"Encrypting {len(data)} bytes of data.")
        encrypted_data = self.cipher_suite.encrypt(data)
        logger.debug(f"Data encrypted to {len(encrypted_data)} bytes.")
        return encrypted_data

    def decrypt_data(self, encrypted_data: bytes) -> bytes | None:
        if not isinstance(encrypted_data, bytes):
             raise TypeError("Data to decrypt must be bytes.")
        if not hasattr(self, 'cipher_suite'):
             logger.error("Decryption attempted before SecurityManager was properly initialized.")
             raise RuntimeError("Cipher suite not available. Check key loading/generation.")
        try:
            logger.debug(f"Decrypting {len(encrypted_data)} bytes of data.")
            decrypted_data = self.cipher_suite.decrypt(encrypted_data)
            logger.debug(f"Data decrypted to {len(decrypted_data)} bytes.")
            return decrypted_data
        except InvalidToken:
            logger.error("Decryption failed: Invalid token. Key might be wrong or data corrupted/tampered.")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during decryption: {e}")
            return None # Or re-raise depending on desired behavior

    def encrypt_file(self, input_file_path: str, output_file_path: str | None = None):
        if not hasattr(self, 'cipher_suite'):
             logger.error("File encryption attempted before SecurityManager was properly initialized.")
             raise RuntimeError("Cipher suite not available. Check key loading/generation.")

        if output_file_path is None:
            output_file_path = input_file_path + ".enc"

        logger.info(f"Encrypting file '{input_file_path}' to '{output_file_path}'")
        try:
            with open(input_file_path, "rb") as f_in:
                data = f_in.read()
            encrypted_data = self.encrypt_data(data) # Reuse data encryption logic
            with open(output_file_path, "wb") as f_out:
                f_out.write(encrypted_data)
            logger.info(f"File '{input_file_path}' successfully encrypted to '{output_file_path}'")
        except FileNotFoundError:
            logger.error(f"Input file not found: {input_file_path}")
            raise
        except IOError as e:
            logger.error(f"File I/O error during encryption: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during file encryption: {e}")
            raise # Re-raise unexpected errors

    def decrypt_file(self, encrypted_file_path: str) -> bytes | None:
        if not hasattr(self, 'cipher_suite'):
             logger.error("File decryption attempted before SecurityManager was properly initialized.")
             raise RuntimeError("Cipher suite not available. Check key loading/generation.")

        logger.info(f"Decrypting file '{encrypted_file_path}'")
        try:
            with open(encrypted_file_path, "rb") as f:
                encrypted_data = f.read()
            decrypted_data = self.decrypt_data(encrypted_data) # Reuse data decryption logic
            if decrypted_data is not None:
                 logger.info(f"File '{encrypted_file_path}' successfully decrypted.")
            else:
                 # Error already logged by decrypt_data
                 logger.warning(f"Failed to decrypt file '{encrypted_file_path}'.")
            return decrypted_data
        except FileNotFoundError:
            logger.error(f"Encrypted file not found: {encrypted_file_path}")
            raise
        except IOError as e:
            logger.error(f"File I/O error during decryption: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during file decryption: {e}")
            return None
    def decrypt_file(self, encrypted_file):
        with open(encrypted_file, "rb") as f:
            encrypted_data = f.read()
        decrypted_data = self.cipher_suite.decrypt(encrypted_data)
        return decrypted_data
