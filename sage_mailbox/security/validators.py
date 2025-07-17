"""
Security validators for sage_mailbox.

This module provides security validation functions for user input,
file uploads, and other security-sensitive operations.
"""

import os
import re
import mimetypes
from typing import List, Optional, Dict, Any, Union
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import gettext_lazy as _
from django.conf import settings

import logging

logger = logging.getLogger(__name__)


class SecurityValidator:
    """
    Main security validator class.
    
    This class provides various security validation methods
    for different types of data and operations.
    """
    
    @staticmethod
    def validate_server_connection(host: str, port: int, use_ssl: bool = True) -> Dict[str, Any]:
        """
        Validate IMAP server connection parameters.
        
        Args:
            host: IMAP server hostname
            port: IMAP server port
            use_ssl: Whether to use SSL/TLS
            
        Returns:
            Dictionary with validation results
        """
        results = {
            'valid': True,
            'warnings': [],
            'errors': [],
        }
        
        # Validate hostname
        if not SecurityValidator.is_valid_hostname(host):
            results['valid'] = False
            results['errors'].append(_('Invalid hostname format'))
            
        # Validate port
        if not (1 <= port <= 65535):
            results['valid'] = False
            results['errors'].append(_('Port must be between 1 and 65535'))
            
        # Check common IMAP ports
        common_ports = {
            143: 'IMAP (non-SSL)',
            993: 'IMAP (SSL)',
            110: 'POP3 (non-SSL)',
            995: 'POP3 (SSL)',
        }
        
        if port in common_ports:
            port_type = common_ports[port]
            if (port in [143, 110] and use_ssl) or (port in [993, 995] and not use_ssl):
                results['warnings'].append(
                    _('Port %(port)s is typically used for %(type)s') % {
                        'port': port,
                        'type': port_type
                    }
                )
        
        # Security warnings
        if not use_ssl:
            results['warnings'].append(_('SSL/TLS is recommended for security'))
            
        if host.lower() in ['localhost', '127.0.0.1', '::1']:
            results['warnings'].append(_('Using localhost may not be accessible from other machines'))
            
        return results
        
    @staticmethod
    def validate_email_address(email: str) -> bool:
        """
        Validate email address format.
        
        Args:
            email: Email address to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            validate_email(email)
            return True
        except ValidationError:
            return False
            
    @staticmethod
    def validate_password_strength(password: str) -> Dict[str, Any]:
        """
        Validate password strength.
        
        Args:
            password: Password to validate
            
        Returns:
            Dictionary with validation results
        """
        results = {
            'valid': True,
            'score': 0,
            'warnings': [],
            'suggestions': [],
        }
        
        if len(password) < 8:
            results['valid'] = False
            results['warnings'].append(_('Password must be at least 8 characters long'))
        else:
            results['score'] += 1
            
        # Check for uppercase letters
        if re.search(r'[A-Z]', password):
            results['score'] += 1
        else:
            results['suggestions'].append(_('Add uppercase letters'))
            
        # Check for lowercase letters
        if re.search(r'[a-z]', password):
            results['score'] += 1
        else:
            results['suggestions'].append(_('Add lowercase letters'))
            
        # Check for numbers
        if re.search(r'\d', password):
            results['score'] += 1
        else:
            results['suggestions'].append(_('Add numbers'))
            
        # Check for special characters
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            results['score'] += 1
        else:
            results['suggestions'].append(_('Add special characters'))
            
        # Check for common patterns
        common_patterns = [
            r'123456',
            r'password',
            r'qwerty',
            r'abc123',
            r'admin',
        ]
        
        for pattern in common_patterns:
            if re.search(pattern, password.lower()):
                results['valid'] = False
                results['warnings'].append(_('Password contains common patterns'))
                break
                
        return results
        
    @staticmethod
    def is_valid_hostname(hostname: str) -> bool:
        """
        Validate hostname format.
        
        Args:
            hostname: Hostname to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not hostname or len(hostname) > 253:
            return False
            
        # Check for valid characters
        if not re.match(r'^[a-zA-Z0-9.-]+$', hostname):
            return False
            
        # Check each label
        labels = hostname.split('.')
        for label in labels:
            if not label or len(label) > 63:
                return False
            if label.startswith('-') or label.endswith('-'):
                return False
                
        return True
        
    @staticmethod
    def validate_file_upload(file_obj, allowed_extensions: Optional[List[str]] = None, 
                           max_size: Optional[int] = None) -> Dict[str, Any]:
        """
        Validate file upload security.
        
        Args:
            file_obj: Uploaded file object
            allowed_extensions: List of allowed file extensions
            max_size: Maximum file size in bytes
            
        Returns:
            Dictionary with validation results
        """
        results = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'file_info': {},
        }
        
        if not file_obj:
            results['valid'] = False
            results['errors'].append(_('No file provided'))
            return results
            
        # Get file information
        filename = file_obj.name
        file_size = file_obj.size
        content_type = getattr(file_obj, 'content_type', '')
        
        results['file_info'] = {
            'filename': filename,
            'size': file_size,
            'content_type': content_type,
        }
        
        # Validate file extension
        if allowed_extensions:
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext not in allowed_extensions:
                results['valid'] = False
                results['errors'].append(
                    _('File extension "%(ext)s" is not allowed') % {'ext': file_ext}
                )
                
        # Validate file size
        if max_size and file_size > max_size:
            results['valid'] = False
            results['errors'].append(
                _('File size exceeds maximum allowed size of %(size)s bytes') % {'size': max_size}
            )
            
        # Validate filename for security
        if not SecurityValidator.is_safe_filename(filename):
            results['valid'] = False
            results['errors'].append(_('Filename contains unsafe characters'))
            
        # Check for suspicious content type
        if content_type:
            if SecurityValidator.is_suspicious_content_type(content_type):
                results['warnings'].append(
                    _('Content type "%(type)s" may be suspicious') % {'type': content_type}
                )
                
        return results
        
    @staticmethod
    def is_safe_filename(filename: str) -> bool:
        """
        Check if filename is safe for storage.
        
        Args:
            filename: Filename to check
            
        Returns:
            True if safe, False otherwise
        """
        if not filename:
            return False
            
        # Check for path traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            return False
            
        # Check for null bytes
        if '\x00' in filename:
            return False
            
        # Check for control characters
        if any(ord(c) < 32 for c in filename):
            return False
            
        # Check for reserved names (Windows)
        reserved_names = [
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        ]
        
        name_without_ext = os.path.splitext(filename)[0].upper()
        if name_without_ext in reserved_names:
            return False
            
        return True
        
    @staticmethod
    def is_suspicious_content_type(content_type: str) -> bool:
        """
        Check if content type is suspicious.
        
        Args:
            content_type: MIME content type
            
        Returns:
            True if suspicious, False otherwise
        """
        suspicious_types = [
            'application/x-msdownload',
            'application/x-msdos-program',
            'application/x-executable',
            'application/x-shockwave-flash',
            'text/html',  # HTML files can be suspicious in email contexts
            'text/javascript',
            'application/javascript',
            'application/x-javascript',
        ]
        
        return content_type.lower() in suspicious_types
        
    @staticmethod
    def validate_url(url: str) -> Dict[str, Any]:
        """
        Validate URL for security.
        
        Args:
            url: URL to validate
            
        Returns:
            Dictionary with validation results
        """
        results = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'url_info': {},
        }
        
        try:
            parsed = urlparse(url)
            
            results['url_info'] = {
                'scheme': parsed.scheme,
                'netloc': parsed.netloc,
                'path': parsed.path,
                'params': parsed.params,
                'query': parsed.query,
                'fragment': parsed.fragment,
            }
            
            # Check scheme
            if parsed.scheme not in ['http', 'https']:
                results['valid'] = False
                results['errors'].append(_('URL scheme must be http or https'))
                
            # Check for localhost/private IPs
            if parsed.netloc.lower() in ['localhost', '127.0.0.1', '::1']:
                results['warnings'].append(_('URL points to localhost'))
                
            # Check for suspicious patterns
            suspicious_patterns = [
                'javascript:',
                'data:',
                'file:',
                'ftp:',
            ]
            
            for pattern in suspicious_patterns:
                if url.lower().startswith(pattern):
                    results['valid'] = False
                    results['errors'].append(
                        _('URL contains suspicious pattern: %(pattern)s') % {'pattern': pattern}
                    )
                    
        except Exception as e:
            results['valid'] = False
            results['errors'].append(_('Invalid URL format'))
            logger.error(f"Error validating URL {url}: {e}")
            
        return results
        
    @staticmethod
    def validate_json_data(data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate JSON data for security.
        
        Args:
            data: JSON data to validate (string or dict)
            
        Returns:
            Dictionary with validation results
        """
        results = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'data_info': {},
        }
        
        try:
            if isinstance(data, str):
                import json
                parsed_data = json.loads(data)
            else:
                parsed_data = data
                
            # Check data size
            data_str = str(parsed_data)
            if len(data_str) > 1024 * 1024:  # 1MB limit
                results['warnings'].append(_('JSON data is very large'))
                
            # Check for suspicious keys
            suspicious_keys = [
                '__proto__',
                'constructor',
                'prototype',
                'eval',
                'function',
                'script',
            ]
            
            def check_keys(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if key.lower() in suspicious_keys:
                            results['warnings'].append(
                                _('Suspicious key found: %(key)s') % {'key': key}
                            )
                        check_keys(value, f"{path}.{key}")
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        check_keys(item, f"{path}[{i}]")
                        
            check_keys(parsed_data)
            
            results['data_info'] = {
                'type': type(parsed_data).__name__,
                'size': len(data_str),
                'keys': list(parsed_data.keys()) if isinstance(parsed_data, dict) else None,
            }
            
        except Exception as e:
            results['valid'] = False
            results['errors'].append(_('Invalid JSON format'))
            logger.error(f"Error validating JSON data: {e}")
            
        return results
        
    @staticmethod
    def sanitize_html(html_content: str) -> str:
        """
        Sanitize HTML content for safe display.
        
        Args:
            html_content: HTML content to sanitize
            
        Returns:
            Sanitized HTML content
        """
        # This is a basic sanitization - for production use,
        # consider using a proper HTML sanitizer like bleach
        
        # Remove script tags
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove dangerous attributes
        dangerous_attrs = [
            'onclick', 'onload', 'onerror', 'onmouseover', 'onmouseout',
            'onfocus', 'onblur', 'onchange', 'onsubmit'
        ]
        
        for attr in dangerous_attrs:
            html_content = re.sub(
                rf'{attr}=["\'][^"\']*["\']',
                '',
                html_content,
                flags=re.IGNORECASE
            )
            
        # Remove javascript: URLs
        html_content = re.sub(r'javascript:[^"\']*', 'about:blank', html_content, flags=re.IGNORECASE)
        
        # Remove data: URLs (optional)
        # html_content = re.sub(r'data:[^"\']*', 'about:blank', html_content, flags=re.IGNORECASE)
        
        return html_content
        
    @staticmethod
    def validate_folder_name(folder_name: str) -> Dict[str, Any]:
        """
        Validate IMAP folder name.
        
        Args:
            folder_name: Folder name to validate
            
        Returns:
            Dictionary with validation results
        """
        results = {
            'valid': True,
            'warnings': [],
            'errors': [],
        }
        
        if not folder_name:
            results['valid'] = False
            results['errors'].append(_('Folder name cannot be empty'))
            return results
            
        # Check length
        if len(folder_name) > 255:
            results['valid'] = False
            results['errors'].append(_('Folder name is too long'))
            
        # Check for invalid characters
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            if char in folder_name:
                results['valid'] = False
                results['errors'].append(
                    _('Folder name contains invalid character: %(char)s') % {'char': char}
                )
                
        # Check for leading/trailing spaces
        if folder_name.startswith(' ') or folder_name.endswith(' '):
            results['warnings'].append(_('Folder name has leading or trailing spaces'))
            
        return results


def validate_input_data(data: Dict[str, Any], validation_rules: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate input data against rules.
    
    Args:
        data: Input data to validate
        validation_rules: Validation rules dictionary
        
    Returns:
        Dictionary with validation results
    """
    results = {
        'valid': True,
        'field_errors': {},
        'general_errors': [],
    }
    
    for field, rules in validation_rules.items():
        field_value = data.get(field)
        field_errors = []
        
        # Required field check
        if rules.get('required', False) and not field_value:
            field_errors.append(_('This field is required'))
            
        if field_value:
            # Type validation
            expected_type = rules.get('type')
            if expected_type and not isinstance(field_value, expected_type):
                field_errors.append(
                    _('Expected type %(type)s') % {'type': expected_type.__name__}
                )
                
            # Length validation
            if isinstance(field_value, str):
                min_length = rules.get('min_length')
                max_length = rules.get('max_length')
                
                if min_length and len(field_value) < min_length:
                    field_errors.append(
                        _('Minimum length is %(length)s') % {'length': min_length}
                    )
                    
                if max_length and len(field_value) > max_length:
                    field_errors.append(
                        _('Maximum length is %(length)s') % {'length': max_length}
                    )
                    
            # Custom validators
            validators = rules.get('validators', [])
            for validator in validators:
                try:
                    validator(field_value)
                except ValidationError as e:
                    field_errors.extend(e.messages)
                    
        if field_errors:
            results['valid'] = False
            results['field_errors'][field] = field_errors
            
    return results 