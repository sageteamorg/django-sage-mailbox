"""
Validators for sage_mailbox application.

This module provides validation functions for email addresses, server configurations,
folder names, and other data validation needs.
"""

import re
import socket
from typing import List, Optional
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, EmailValidator
from django.utils.translation import gettext_lazy as _

# Email validation
email_validator = EmailValidator()


def validate_email_address(value: str) -> None:
    """
    Validate email address format.
    
    Args:
        value: Email address to validate
        
    Raises:
        ValidationError: If email format is invalid
    """
    if not value:
        return
    
    try:
        email_validator(value)
    except ValidationError:
        raise ValidationError(_("Enter a valid email address."))


def validate_email_list(value: List[str]) -> None:
    """
    Validate a list of email addresses.
    
    Args:
        value: List of email addresses to validate
        
    Raises:
        ValidationError: If any email format is invalid
    """
    if not value:
        return
    
    invalid_emails = []
    for email in value:
        if email:  # Skip empty strings
            try:
                validate_email_address(email)
            except ValidationError:
                invalid_emails.append(email)
    
    if invalid_emails:
        raise ValidationError(
            _("Invalid email addresses: %(emails)s"),
            params={'emails': ', '.join(invalid_emails)}
        )


def validate_comma_separated_emails(value: str) -> None:
    """
    Validate comma-separated email addresses.
    
    Args:
        value: Comma-separated email addresses
        
    Raises:
        ValidationError: If any email format is invalid
    """
    if not value:
        return
    
    emails = [email.strip() for email in value.split(',')]
    validate_email_list(emails)


# Server configuration validation
def validate_hostname(value: str) -> None:
    """
    Validate hostname or IP address.
    
    Args:
        value: Hostname or IP address to validate
        
    Raises:
        ValidationError: If hostname is invalid
    """
    if not value:
        raise ValidationError(_("Hostname cannot be empty."))
    
    # Check if it's a valid IP address
    try:
        socket.inet_aton(value)
        return  # Valid IP address
    except socket.error:
        pass
    
    # Check if it's a valid hostname
    hostname_pattern = re.compile(
        r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
    )
    
    if not hostname_pattern.match(value):
        raise ValidationError(_("Enter a valid hostname or IP address."))


def validate_port(value: int) -> None:
    """
    Validate port number.
    
    Args:
        value: Port number to validate
        
    Raises:
        ValidationError: If port is invalid
    """
    if not isinstance(value, int):
        raise ValidationError(_("Port must be an integer."))
    
    if value < 1 or value > 65535:
        raise ValidationError(_("Port must be between 1 and 65535."))


def validate_timeout(value: float) -> None:
    """
    Validate timeout value.
    
    Args:
        value: Timeout value to validate
        
    Raises:
        ValidationError: If timeout is invalid
    """
    if not isinstance(value, (int, float)):
        raise ValidationError(_("Timeout must be a number."))
    
    if value <= 0:
        raise ValidationError(_("Timeout must be greater than 0."))
    
    if value > 300:  # 5 minutes max
        raise ValidationError(_("Timeout cannot exceed 300 seconds."))


def validate_server_connection(host: str, port: int, timeout: float = 10.0) -> None:
    """
    Validate server connection by attempting to connect.
    
    Args:
        host: Server hostname or IP
        port: Server port
        timeout: Connection timeout
        
    Raises:
        ValidationError: If connection fails
    """
    try:
        socket.setdefaulttimeout(timeout)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result != 0:
            raise ValidationError(
                _("Cannot connect to server %(host)s:%(port)s"),
                params={'host': host, 'port': port}
            )
    except socket.gaierror:
        raise ValidationError(
            _("Cannot resolve hostname: %(host)s"),
            params={'host': host}
        )
    except Exception as e:
        raise ValidationError(
            _("Connection error: %(error)s"),
            params={'error': str(e)}
        )


# Folder/Mailbox validation
def validate_folder_name(value: str) -> None:
    """
    Validate IMAP folder name.
    
    Args:
        value: Folder name to validate
        
    Raises:
        ValidationError: If folder name is invalid
    """
    if not value:
        raise ValidationError(_("Folder name cannot be empty."))
    
    # Check length
    if len(value) > 255:
        raise ValidationError(_("Folder name cannot exceed 255 characters."))
    
    # Check for invalid characters
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in invalid_chars:
        if char in value:
            raise ValidationError(
                _("Folder name contains invalid character: %(char)s"),
                params={'char': char}
            )
    
    # Check for reserved names
    reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
                      'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
                      'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
    
    if value.upper() in reserved_names:
        raise ValidationError(
            _("Folder name '%(name)s' is reserved."),
            params={'name': value}
        )


def validate_folder_hierarchy(value: str, delimiter: str = '/') -> None:
    """
    Validate folder hierarchy path.
    
    Args:
        value: Folder hierarchy path
        delimiter: Hierarchy delimiter
        
    Raises:
        ValidationError: If hierarchy is invalid
    """
    if not value:
        return
    
    # Split by delimiter and validate each part
    parts = value.split(delimiter)
    for part in parts:
        if part:  # Skip empty parts
            validate_folder_name(part)
    
    # Check for double delimiters
    if delimiter + delimiter in value:
        raise ValidationError(
            _("Folder hierarchy contains double delimiters."),
        )


# Message validation
def validate_message_id(value: str) -> None:
    """
    Validate email Message-ID format.
    
    Args:
        value: Message ID to validate
        
    Raises:
        ValidationError: If Message-ID format is invalid
    """
    if not value:
        return
    
    # Message-ID should be in format <local-part@domain>
    message_id_pattern = re.compile(
        r'^<[^<>@]+@[^<>@]+>$'
    )
    
    if not message_id_pattern.match(value):
        raise ValidationError(_("Invalid Message-ID format."))


def validate_subject(value: str) -> None:
    """
    Validate email subject.
    
    Args:
        value: Subject to validate
        
    Raises:
        ValidationError: If subject is invalid
    """
    if not value:
        return
    
    # Check length (RFC 5322 suggests 78 characters per line)
    if len(value) > 1000:
        raise ValidationError(_("Subject is too long (maximum 1000 characters)."))
    
    # Check for control characters
    control_chars = ['\x00', '\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07', 
                     '\x08', '\x0B', '\x0C', '\x0E', '\x0F', '\x10', '\x11', '\x12', 
                     '\x13', '\x14', '\x15', '\x16', '\x17', '\x18', '\x19', '\x1A', 
                     '\x1B', '\x1C', '\x1D', '\x1E', '\x1F', '\x7F']
    
    for char in control_chars:
        if char in value:
            raise ValidationError(_("Subject contains invalid control characters."))


def validate_uid(value: int) -> None:
    """
    Validate IMAP UID.
    
    Args:
        value: UID to validate
        
    Raises:
        ValidationError: If UID is invalid
    """
    if not isinstance(value, int):
        raise ValidationError(_("UID must be an integer."))
    
    if value < 1:
        raise ValidationError(_("UID must be greater than 0."))
    
    if value > 4294967295:  # 2^32 - 1
        raise ValidationError(_("UID is too large."))


def validate_uid_list(value: List[int]) -> None:
    """
    Validate a list of UIDs.
    
    Args:
        value: List of UIDs to validate
        
    Raises:
        ValidationError: If any UID is invalid
    """
    if not value:
        return
    
    invalid_uids = []
    for uid in value:
        try:
            validate_uid(uid)
        except ValidationError:
            invalid_uids.append(uid)
    
    if invalid_uids:
        raise ValidationError(
            _("Invalid UIDs: %(uids)s"),
            params={'uids': ', '.join(map(str, invalid_uids))}
        )


# File validation
def validate_file_size(value: int, max_size: int = 25 * 1024 * 1024) -> None:
    """
    Validate file size.
    
    Args:
        value: File size in bytes
        max_size: Maximum allowed size in bytes (default: 25MB)
        
    Raises:
        ValidationError: If file size is invalid
    """
    if not isinstance(value, int):
        raise ValidationError(_("File size must be an integer."))
    
    if value < 0:
        raise ValidationError(_("File size cannot be negative."))
    
    if value > max_size:
        max_size_mb = max_size / (1024 * 1024)
        raise ValidationError(
            _("File size cannot exceed %(size)sMB."),
            params={'size': max_size_mb}
        )


def validate_filename(value: str) -> None:
    """
    Validate filename for security.
    
    Args:
        value: Filename to validate
        
    Raises:
        ValidationError: If filename is invalid
    """
    if not value:
        raise ValidationError(_("Filename cannot be empty."))
    
    # Check length
    if len(value) > 255:
        raise ValidationError(_("Filename cannot exceed 255 characters."))
    
    # Check for path traversal attempts
    if '..' in value or '/' in value or '\\' in value:
        raise ValidationError(_("Filename contains invalid path characters."))
    
    # Check for invalid characters
    invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '\x00']
    for char in invalid_chars:
        if char in value:
            raise ValidationError(
                _("Filename contains invalid character: %(char)s"),
                params={'char': char}
            )
    
    # Check for reserved names
    reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
                      'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
                      'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
    
    name_without_ext = value.split('.')[0].upper()
    if name_without_ext in reserved_names:
        raise ValidationError(
            _("Filename '%(name)s' is reserved."),
            params={'name': value}
        )


def validate_content_type(value: str) -> None:
    """
    Validate MIME content type.
    
    Args:
        value: Content type to validate
        
    Raises:
        ValidationError: If content type is invalid
    """
    if not value:
        raise ValidationError(_("Content type cannot be empty."))
    
    # Basic MIME type pattern
    mime_pattern = re.compile(
        r'^[a-zA-Z0-9][a-zA-Z0-9!#$&\-\^_]*\/[a-zA-Z0-9][a-zA-Z0-9!#$&\-\^_]*'
        r'(\s*;\s*[a-zA-Z0-9][a-zA-Z0-9!#$&\-\^_]*=[a-zA-Z0-9!#$&\-\^_]*)*$'
    )
    
    if not mime_pattern.match(value):
        raise ValidationError(_("Invalid content type format."))


# Password validation
def validate_password_strength(value: str) -> None:
    """
    Validate password strength.
    
    Args:
        value: Password to validate
        
    Raises:
        ValidationError: If password is too weak
    """
    if not value:
        raise ValidationError(_("Password cannot be empty."))
    
    if len(value) < 8:
        raise ValidationError(_("Password must be at least 8 characters long."))
    
    if len(value) > 128:
        raise ValidationError(_("Password cannot exceed 128 characters."))
    
    # Check for common weak passwords
    weak_passwords = [
        'password', '123456', '12345678', 'qwerty', 'abc123',
        'password123', 'admin', 'letmein', 'welcome', 'monkey'
    ]
    
    if value.lower() in weak_passwords:
        raise ValidationError(_("Password is too common."))


# JSON validation
def validate_json_headers(value: dict) -> None:
    """
    Validate email headers JSON.
    
    Args:
        value: Headers dictionary to validate
        
    Raises:
        ValidationError: If headers are invalid
    """
    if not isinstance(value, dict):
        raise ValidationError(_("Headers must be a dictionary."))
    
    for key, val in value.items():
        if not isinstance(key, str):
            raise ValidationError(_("Header keys must be strings."))
        
        if not isinstance(val, str):
            raise ValidationError(_("Header values must be strings."))
        
        # Check for control characters in header values
        if any(ord(c) < 32 or ord(c) > 126 for c in val if c not in ['\t', '\n', '\r']):
            raise ValidationError(
                _("Header '%(key)s' contains invalid characters."),
                params={'key': key}
            )


# Regex validators for common patterns
folder_name_validator = RegexValidator(
    regex=r'^[a-zA-Z0-9._-]+$',
    message=_("Folder name can only contain letters, numbers, dots, hyphens, and underscores."),
    code='invalid_folder_name'
)

server_name_validator = RegexValidator(
    regex=r'^[a-zA-Z0-9._-]+$',
    message=_("Server name can only contain letters, numbers, dots, hyphens, and underscores."),
    code='invalid_server_name'
)

# Composite validators
def validate_imap_server_config(host: str, port: int, username: str, password: str, 
                               timeout: float = 30.0, test_connection: bool = False) -> None:
    """
    Validate complete IMAP server configuration.
    
    Args:
        host: Server hostname
        port: Server port
        username: Username
        password: Password
        timeout: Connection timeout
        test_connection: Whether to test actual connection
        
    Raises:
        ValidationError: If configuration is invalid
    """
    validate_hostname(host)
    validate_port(port)
    validate_timeout(timeout)
    
    if not username:
        raise ValidationError(_("Username cannot be empty."))
    
    if not password:
        raise ValidationError(_("Password cannot be empty."))
    
    if test_connection:
        validate_server_connection(host, port, timeout)


def validate_email_complete(subject: str, from_address: str, to_addresses: List[str],
                           cc_addresses: Optional[List[str]] = None,
                           bcc_addresses: Optional[List[str]] = None,
                           message_id: Optional[str] = None) -> None:
    """
    Validate complete email data.
    
    Args:
        subject: Email subject
        from_address: From address
        to_addresses: To addresses
        cc_addresses: CC addresses
        bcc_addresses: BCC addresses
        message_id: Message ID
        
    Raises:
        ValidationError: If email data is invalid
    """
    validate_subject(subject)
    validate_email_address(from_address)
    validate_email_list(to_addresses)
    
    if cc_addresses:
        validate_email_list(cc_addresses)
    
    if bcc_addresses:
        validate_email_list(bcc_addresses)
    
    if message_id:
        validate_message_id(message_id) 