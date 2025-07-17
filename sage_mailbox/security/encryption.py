"""
Encryption utilities for sage_mailbox.

This module provides encryption and decryption functions for passwords,
email content, and sensitive data storage.
"""

import base64
import hashlib
import hmac
import os
import secrets
from typing import Optional, Tuple, Union

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

import logging

logger = logging.getLogger(__name__)


class PasswordEncryption:
    """
    Utility class for encrypting and decrypting passwords.
    
    This class provides secure password storage and retrieval
    for IMAP server credentials and other sensitive data.
    """
    
    def __init__(self):
        self.key = self._get_or_create_key()
        self.fernet = Fernet(self.key)
        
    def _get_or_create_key(self) -> bytes:
        """Get or create encryption key from settings."""
        # Try to get key from settings
        key_setting = getattr(settings, 'SAGE_MAILBOX_ENCRYPTION_KEY', None)
        
        if key_setting:
            try:
                return base64.urlsafe_b64decode(key_setting)
            except Exception as e:
                logger.error(f"Invalid encryption key in settings: {e}")
                raise ImproperlyConfigured("Invalid SAGE_MAILBOX_ENCRYPTION_KEY format")
        
        # Generate key from SECRET_KEY
        secret_key = getattr(settings, 'SECRET_KEY', None)
        if not secret_key:
            raise ImproperlyConfigured("SECRET_KEY is required for encryption")
            
        # Derive key from SECRET_KEY
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'sage_mailbox_salt',  # Fixed salt for consistency
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
        return key
        
    def encrypt_password(self, password: str) -> str:
        """
        Encrypt a password for storage.
        
        Args:
            password: Plain text password to encrypt
            
        Returns:
            Encrypted password as base64 string
        """
        try:
            if not password:
                return ""
                
            encrypted = self.fernet.encrypt(password.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
            
        except Exception as e:
            logger.error(f"Failed to encrypt password: {e}")
            raise
            
    def decrypt_password(self, encrypted_password: str) -> str:
        """
        Decrypt an encrypted password.
        
        Args:
            encrypted_password: Encrypted password as base64 string
            
        Returns:
            Decrypted plain text password
        """
        try:
            if not encrypted_password:
                return ""
                
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_password.encode())
            decrypted = self.fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
            
        except Exception as e:
            logger.error(f"Failed to decrypt password: {e}")
            raise
            
    def verify_password(self, password: str, encrypted_password: str) -> bool:
        """
        Verify a password against its encrypted version.
        
        Args:
            password: Plain text password to verify
            encrypted_password: Encrypted password to compare against
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            decrypted = self.decrypt_password(encrypted_password)
            return password == decrypted
        except Exception:
            return False
            
    def generate_secure_password(self, length: int = 16) -> str:
        """
        Generate a secure random password.
        
        Args:
            length: Length of password to generate
            
        Returns:
            Secure random password
        """
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))


class EmailContentEncryption:
    """
    Utility class for encrypting email content.
    
    This class provides encryption for email content, attachments,
    and other sensitive email data.
    """
    
    def __init__(self):
        self.key = self._get_content_key()
        self.fernet = Fernet(self.key)
        
    def _get_content_key(self) -> bytes:
        """Get encryption key for email content."""
        # Use a different key derivation for content encryption
        secret_key = getattr(settings, 'SECRET_KEY', None)
        if not secret_key:
            raise ImproperlyConfigured("SECRET_KEY is required for content encryption")
            
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'email_content_salt',  # Different salt for content
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
        return key
        
    def encrypt_content(self, content: Union[str, bytes]) -> str:
        """
        Encrypt email content.
        
        Args:
            content: Email content to encrypt (str or bytes)
            
        Returns:
            Encrypted content as base64 string
        """
        try:
            if isinstance(content, str):
                content = content.encode('utf-8')
            elif content is None:
                return ""
                
            encrypted = self.fernet.encrypt(content)
            return base64.urlsafe_b64encode(encrypted).decode()
            
        except Exception as e:
            logger.error(f"Failed to encrypt content: {e}")
            raise
            
    def decrypt_content(self, encrypted_content: str) -> bytes:
        """
        Decrypt email content.
        
        Args:
            encrypted_content: Encrypted content as base64 string
            
        Returns:
            Decrypted content as bytes
        """
        try:
            if not encrypted_content:
                return b""
                
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_content.encode())
            decrypted = self.fernet.decrypt(encrypted_bytes)
            return decrypted
            
        except Exception as e:
            logger.error(f"Failed to decrypt content: {e}")
            raise
            
    def decrypt_content_to_string(self, encrypted_content: str) -> str:
        """
        Decrypt email content to string.
        
        Args:
            encrypted_content: Encrypted content as base64 string
            
        Returns:
            Decrypted content as string
        """
        decrypted_bytes = self.decrypt_content(encrypted_content)
        return decrypted_bytes.decode('utf-8')


class AttachmentEncryption:
    """
    Utility class for encrypting attachment files.
    
    This class provides encryption for attachment files stored on disk.
    """
    
    def __init__(self):
        self.key = self._get_attachment_key()
        
    def _get_attachment_key(self) -> bytes:
        """Get encryption key for attachments."""
        secret_key = getattr(settings, 'SECRET_KEY', None)
        if not secret_key:
            raise ImproperlyConfigured("SECRET_KEY is required for attachment encryption")
            
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'attachment_salt',  # Different salt for attachments
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(secret_key.encode())
        
    def encrypt_file(self, file_data: bytes) -> Tuple[bytes, bytes]:
        """
        Encrypt file data using AES-256-GCM.
        
        Args:
            file_data: File data to encrypt
            
        Returns:
            Tuple of (encrypted_data, nonce)
        """
        try:
            # Generate random nonce
            nonce = os.urandom(12)
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.GCM(nonce),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            
            # Encrypt data
            encrypted_data = encryptor.update(file_data) + encryptor.finalize()
            
            # Return encrypted data with authentication tag
            return encrypted_data + encryptor.tag, nonce
            
        except Exception as e:
            logger.error(f"Failed to encrypt file: {e}")
            raise
            
    def decrypt_file(self, encrypted_data: bytes, nonce: bytes) -> bytes:
        """
        Decrypt file data using AES-256-GCM.
        
        Args:
            encrypted_data: Encrypted file data (includes auth tag)
            nonce: Nonce used for encryption
            
        Returns:
            Decrypted file data
        """
        try:
            # Split encrypted data and authentication tag
            auth_tag = encrypted_data[-16:]  # Last 16 bytes
            encrypted_data = encrypted_data[:-16]  # Everything except last 16 bytes
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.GCM(nonce, auth_tag),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            # Decrypt data
            decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
            return decrypted_data
            
        except Exception as e:
            logger.error(f"Failed to decrypt file: {e}")
            raise


class SecureTokenGenerator:
    """
    Utility class for generating secure tokens.
    
    This class provides secure token generation for various purposes
    like API keys, session tokens, etc.
    """
    
    @staticmethod
    def generate_api_key(length: int = 32) -> str:
        """
        Generate a secure API key.
        
        Args:
            length: Length of the key in bytes
            
        Returns:
            Secure API key as hex string
        """
        return secrets.token_hex(length)
        
    @staticmethod
    def generate_session_token(length: int = 32) -> str:
        """
        Generate a secure session token.
        
        Args:
            length: Length of the token in bytes
            
        Returns:
            Secure session token as URL-safe base64 string
        """
        return secrets.token_urlsafe(length)
        
    @staticmethod
    def generate_csrf_token(length: int = 32) -> str:
        """
        Generate a secure CSRF token.
        
        Args:
            length: Length of the token in bytes
            
        Returns:
            Secure CSRF token as hex string
        """
        return secrets.token_hex(length)
        
    @staticmethod
    def verify_token_format(token: str, expected_length: int = 64) -> bool:
        """
        Verify token format and length.
        
        Args:
            token: Token to verify
            expected_length: Expected token length (for hex tokens)
            
        Returns:
            True if token format is valid, False otherwise
        """
        try:
            # Check if token is valid hex
            int(token, 16)
            return len(token) == expected_length
        except ValueError:
            return False


class HashingUtility:
    """
    Utility class for hashing operations.
    
    This class provides secure hashing for data integrity
    and verification purposes.
    """
    
    @staticmethod
    def hash_data(data: Union[str, bytes], algorithm: str = 'sha256') -> str:
        """
        Hash data using specified algorithm.
        
        Args:
            data: Data to hash
            algorithm: Hash algorithm ('sha256', 'sha512', 'md5')
            
        Returns:
            Hex digest of the hash
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
            
        if algorithm == 'sha256':
            return hashlib.sha256(data).hexdigest()
        elif algorithm == 'sha512':
            return hashlib.sha512(data).hexdigest()
        elif algorithm == 'md5':
            return hashlib.md5(data).hexdigest()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")
            
    @staticmethod
    def verify_hash(data: Union[str, bytes], expected_hash: str, algorithm: str = 'sha256') -> bool:
        """
        Verify data against expected hash.
        
        Args:
            data: Data to verify
            expected_hash: Expected hash value
            algorithm: Hash algorithm used
            
        Returns:
            True if hash matches, False otherwise
        """
        try:
            actual_hash = HashingUtility.hash_data(data, algorithm)
            return hmac.compare_digest(actual_hash, expected_hash)
        except Exception:
            return False
            
    @staticmethod
    def generate_file_checksum(file_path: str, algorithm: str = 'sha256') -> str:
        """
        Generate checksum for a file.
        
        Args:
            file_path: Path to the file
            algorithm: Hash algorithm to use
            
        Returns:
            File checksum as hex string
        """
        hash_obj = getattr(hashlib, algorithm)()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
                
        return hash_obj.hexdigest()


def get_encryption_key_info() -> dict:
    """
    Get information about encryption keys (for debugging/admin).
    
    Returns:
        Dictionary with encryption key information
    """
    try:
        password_enc = PasswordEncryption()
        content_enc = EmailContentEncryption()
        
        # Generate sample encrypted data to verify keys work
        test_password = "test_password_123"
        test_content = "test_content_456"
        
        encrypted_password = password_enc.encrypt_password(test_password)
        encrypted_content = content_enc.encrypt_content(test_content)
        
        # Verify decryption works
        decrypted_password = password_enc.decrypt_password(encrypted_password)
        decrypted_content = content_enc.decrypt_content_to_string(encrypted_content)
        
        return {
            'password_encryption': decrypted_password == test_password,
            'content_encryption': decrypted_content == test_content,
            'key_derivation': 'PBKDF2-SHA256',
            'encryption_algorithm': 'Fernet (AES-128-CBC + HMAC-SHA256)',
            'key_length': 32,
            'iterations': 100000,
        }
        
    except Exception as e:
        logger.error(f"Error getting encryption key info: {e}")
        return {'error': str(e)}


def secure_compare(a: str, b: str) -> bool:
    """
    Secure string comparison to prevent timing attacks.
    
    Args:
        a: First string
        b: Second string
        
    Returns:
        True if strings are equal, False otherwise
    """
    return hmac.compare_digest(a, b)


def generate_encryption_key() -> str:
    """
    Generate a new encryption key for use in settings.
    
    Returns:
        Base64-encoded encryption key
    """
    key = Fernet.generate_key()
    return base64.urlsafe_b64encode(key).decode()


# Initialize encryption utilities
password_encryption = PasswordEncryption()
email_content_encryption = EmailContentEncryption()
attachment_encryption = AttachmentEncryption()
token_generator = SecureTokenGenerator()
hashing_utility = HashingUtility() 