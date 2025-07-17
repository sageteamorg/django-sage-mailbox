"""
Django system checks for sage_mailbox application.

This module provides system checks for validating settings and configuration
for the sage_mailbox application.
"""

import os
import socket
from typing import List, Optional

from django.conf import settings
from django.core.checks import Error, Warning, Info, register, Tags
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

from .validators import (
    validate_hostname, validate_port, validate_timeout,
    validate_file_size, validate_folder_name
)


@register(Tags.compatibility)
def check_required_packages(app_configs, **kwargs):
    """Check that required packages are installed."""
    errors = []
    
    # Check for sage_imap
    try:
        import sage_imap
    except ImportError:
        errors.append(
            Error(
                'sage_imap package is required but not installed.',
                hint='Install sage_imap package: pip install sage-imap',
                id='sage_mailbox.E001',
            )
        )
    
    # Check for django-jsonform if JSON forms are enabled
    if getattr(settings, 'SAGE_MAILBOX_USE_JSON_FORMS', True):
        try:
            import django_jsonform
        except ImportError:
            errors.append(
                Warning(
                    'django-jsonform package is recommended for better JSON field support.',
                    hint='Install django-jsonform: pip install django-jsonform',
                    id='sage_mailbox.W001',
                )
            )
    
    return errors


@register(Tags.compatibility)
def check_database_backend(app_configs, **kwargs):
    """Check database backend compatibility."""
    errors = []
    
    # Get default database backend
    default_db = settings.DATABASES.get('default', {})
    engine = default_db.get('ENGINE', '')
    
    # Check for PostgreSQL (recommended for JSON fields)
    if 'postgresql' not in engine.lower():
        errors.append(
            Warning(
                'PostgreSQL is recommended for optimal JSON field support.',
                hint='Consider using PostgreSQL for better JSON field performance and features.',
                id='sage_mailbox.W002',
            )
        )
    
    # Check for SQLite in production
    if 'sqlite' in engine.lower() and not settings.DEBUG:
        errors.append(
            Warning(
                'SQLite is not recommended for production use.',
                hint='Consider using PostgreSQL or MySQL for production deployments.',
                id='sage_mailbox.W003',
            )
        )
    
    return errors


@register(Tags.security)
def check_security_settings(app_configs, **kwargs):
    """Check security-related settings."""
    errors = []
    
    # Check for encryption settings
    if not getattr(settings, 'SAGE_MAILBOX_ENCRYPT_PASSWORDS', True):
        errors.append(
            Warning(
                'Password encryption is disabled.',
                hint='Enable SAGE_MAILBOX_ENCRYPT_PASSWORDS for better security.',
                id='sage_mailbox.W004',
            )
        )
    
    # Check for secure file storage
    media_root = getattr(settings, 'MEDIA_ROOT', '')
    if media_root and not os.path.isabs(media_root):
        errors.append(
            Warning(
                'MEDIA_ROOT should be an absolute path.',
                hint='Use absolute path for MEDIA_ROOT to prevent security issues.',
                id='sage_mailbox.W005',
            )
        )
    
    # Check for secure file uploads
    max_upload_size = getattr(settings, 'SAGE_MAILBOX_MAX_ATTACHMENT_SIZE', 25 * 1024 * 1024)
    if max_upload_size > 100 * 1024 * 1024:  # 100MB
        errors.append(
            Warning(
                'Maximum attachment size is very large.',
                hint='Consider reducing SAGE_MAILBOX_MAX_ATTACHMENT_SIZE for security.',
                id='sage_mailbox.W006',
            )
        )
    
    return errors


@register(Tags.compatibility)
def check_email_settings(app_configs, **kwargs):
    """Check email-related settings."""
    errors = []
    
    # Check for default email backend
    email_backend = getattr(settings, 'EMAIL_BACKEND', '')
    if 'console' in email_backend.lower() and not settings.DEBUG:
        errors.append(
            Warning(
                'Console email backend is used in production.',
                hint='Configure proper email backend for production.',
                id='sage_mailbox.W007',
            )
        )
    
    # Check for email timeout settings
    email_timeout = getattr(settings, 'EMAIL_TIMEOUT', 30)
    if email_timeout < 10:
        errors.append(
            Warning(
                'Email timeout is very short.',
                hint='Consider increasing EMAIL_TIMEOUT for better reliability.',
                id='sage_mailbox.W008',
            )
        )
    
    return errors


@register(Tags.compatibility)
def check_sage_mailbox_settings(app_configs, **kwargs):
    """Check sage_mailbox specific settings."""
    errors = []
    
    # Check sync settings
    sync_batch_size = getattr(settings, 'SAGE_MAILBOX_SYNC_BATCH_SIZE', 50)
    if sync_batch_size > 1000:
        errors.append(
            Warning(
                'Sync batch size is very large.',
                hint='Consider reducing SAGE_MAILBOX_SYNC_BATCH_SIZE for better performance.',
                id='sage_mailbox.W009',
            )
        )
    
    # Check attachment storage settings
    attachment_storage = getattr(settings, 'SAGE_MAILBOX_ATTACHMENT_STORAGE', None)
    if attachment_storage and not hasattr(settings, attachment_storage):
        errors.append(
            Error(
                f'Attachment storage setting {attachment_storage} is not configured.',
                hint='Configure the specified attachment storage backend.',
                id='sage_mailbox.E002',
            )
        )
    
    # Check cleanup settings
    cleanup_days = getattr(settings, 'SAGE_MAILBOX_CLEANUP_DAYS', 30)
    if cleanup_days < 1:
        errors.append(
            Warning(
                'Cleanup days is too short.',
                hint='Consider increasing SAGE_MAILBOX_CLEANUP_DAYS to prevent data loss.',
                id='sage_mailbox.W010',
            )
        )
    
    return errors


@register(Tags.compatibility)
def check_storage_settings(app_configs, **kwargs):
    """Check storage-related settings."""
    errors = []
    
    # Check media root
    media_root = getattr(settings, 'MEDIA_ROOT', '')
    if not media_root:
        errors.append(
            Error(
                'MEDIA_ROOT is not configured.',
                hint='Configure MEDIA_ROOT for file storage.',
                id='sage_mailbox.E003',
            )
        )
    elif not os.path.exists(media_root):
        errors.append(
            Warning(
                f'MEDIA_ROOT directory does not exist: {media_root}',
                hint='Create the MEDIA_ROOT directory or ensure it exists.',
                id='sage_mailbox.W011',
            )
        )
    elif not os.access(media_root, os.W_OK):
        errors.append(
            Error(
                f'MEDIA_ROOT directory is not writable: {media_root}',
                hint='Ensure the MEDIA_ROOT directory is writable by the web server.',
                id='sage_mailbox.E004',
            )
        )
    
    # Check static root for admin files
    static_root = getattr(settings, 'STATIC_ROOT', '')
    if not static_root and not settings.DEBUG:
        errors.append(
            Warning(
                'STATIC_ROOT is not configured for production.',
                hint='Configure STATIC_ROOT for production deployment.',
                id='sage_mailbox.W012',
            )
        )
    
    return errors


@register(Tags.compatibility)
def check_cache_settings(app_configs, **kwargs):
    """Check cache-related settings."""
    errors = []
    
    # Check for cache backend
    caches = getattr(settings, 'CACHES', {})
    default_cache = caches.get('default', {})
    
    if default_cache.get('BACKEND') == 'django.core.cache.backends.dummy.DummyCache':
        errors.append(
            Warning(
                'Dummy cache backend is used.',
                hint='Configure proper cache backend for better performance.',
                id='sage_mailbox.W013',
            )
        )
    
    return errors


@register(Tags.compatibility)
def check_logging_settings(app_configs, **kwargs):
    """Check logging configuration."""
    errors = []
    
    # Check for logging configuration
    logging_config = getattr(settings, 'LOGGING', {})
    
    # Check for sage_mailbox logger
    loggers = logging_config.get('loggers', {})
    if 'sage_mailbox' not in loggers:
        errors.append(
            Info(
                'sage_mailbox logger is not configured.',
                hint='Add sage_mailbox logger to LOGGING configuration for better debugging.',
                id='sage_mailbox.I001',
            )
        )
    
    # Check for appropriate log level
    if settings.DEBUG:
        root_logger = loggers.get('', {})
        if root_logger.get('level', 'INFO') not in ['DEBUG', 'INFO']:
            errors.append(
                Info(
                    'Consider using DEBUG or INFO log level in development.',
                    hint='Set appropriate log level for development debugging.',
                    id='sage_mailbox.I002',
                )
            )
    
    return errors


@register(Tags.compatibility)
def check_timezone_settings(app_configs, **kwargs):
    """Check timezone configuration."""
    errors = []
    
    # Check for timezone awareness
    if not settings.USE_TZ:
        errors.append(
            Warning(
                'Timezone support is disabled.',
                hint='Enable USE_TZ for proper timezone handling in email dates.',
                id='sage_mailbox.W014',
            )
        )
    
    # Check for appropriate timezone
    timezone = getattr(settings, 'TIME_ZONE', 'UTC')
    if timezone == 'UTC' and not settings.DEBUG:
        errors.append(
            Info(
                'Using UTC timezone.',
                hint='Consider setting appropriate timezone for your application.',
                id='sage_mailbox.I003',
            )
        )
    
    return errors


@register(Tags.compatibility)
def check_internationalization_settings(app_configs, **kwargs):
    """Check internationalization configuration."""
    errors = []
    
    # Check for i18n support
    if not settings.USE_I18N:
        errors.append(
            Warning(
                'Internationalization is disabled.',
                hint='Enable USE_I18N for proper localization support.',
                id='sage_mailbox.W015',
            )
        )
    
    # Check for sage_mailbox in locale paths
    locale_paths = getattr(settings, 'LOCALE_PATHS', [])
    sage_mailbox_locale = None
    
    for path in locale_paths:
        if 'sage_mailbox' in str(path):
            sage_mailbox_locale = path
            break
    
    if not sage_mailbox_locale:
        errors.append(
            Info(
                'sage_mailbox locale path is not configured.',
                hint='Add sage_mailbox locale path to LOCALE_PATHS for translations.',
                id='sage_mailbox.I004',
            )
        )
    
    return errors


@register(Tags.compatibility)
def check_admin_settings(app_configs, **kwargs):
    """Check Django admin configuration."""
    errors = []
    
    # Check if admin is enabled
    installed_apps = getattr(settings, 'INSTALLED_APPS', [])
    if 'django.contrib.admin' not in installed_apps:
        errors.append(
            Warning(
                'Django admin is not installed.',
                hint='Install django.contrib.admin to use sage_mailbox admin interface.',
                id='sage_mailbox.W016',
            )
        )
    
    # Check for admin media files
    if 'django.contrib.staticfiles' not in installed_apps:
        errors.append(
            Warning(
                'Django staticfiles is not installed.',
                hint='Install django.contrib.staticfiles for proper admin styling.',
                id='sage_mailbox.W017',
            )
        )
    
    return errors


@register(Tags.compatibility)
def check_middleware_settings(app_configs, **kwargs):
    """Check middleware configuration."""
    errors = []
    
    middleware = getattr(settings, 'MIDDLEWARE', [])
    
    # Check for security middleware
    if 'django.middleware.security.SecurityMiddleware' not in middleware:
        errors.append(
            Warning(
                'Security middleware is not installed.',
                hint='Add SecurityMiddleware for better security.',
                id='sage_mailbox.W018',
            )
        )
    
    # Check for session middleware (required for admin)
    if 'django.contrib.sessions.middleware.SessionMiddleware' not in middleware:
        errors.append(
            Warning(
                'Session middleware is not installed.',
                hint='Add SessionMiddleware for admin authentication.',
                id='sage_mailbox.W019',
            )
        )
    
    return errors


def validate_imap_server_settings(host: str, port: int, username: str, password: str,
                                 use_ssl: bool = True, timeout: float = 30.0) -> List[str]:
    """
    Validate IMAP server settings.
    
    Args:
        host: IMAP server hostname
        port: IMAP server port
        username: Username for authentication
        password: Password for authentication
        use_ssl: Whether to use SSL
        timeout: Connection timeout
        
    Returns:
        List of validation errors
    """
    errors = []
    
    try:
        validate_hostname(host)
    except Exception as e:
        errors.append(f"Invalid hostname: {e}")
    
    try:
        validate_port(port)
    except Exception as e:
        errors.append(f"Invalid port: {e}")
    
    try:
        validate_timeout(timeout)
    except Exception as e:
        errors.append(f"Invalid timeout: {e}")
    
    if not username:
        errors.append("Username cannot be empty")
    
    if not password:
        errors.append("Password cannot be empty")
    
    # Check standard IMAP ports
    if use_ssl and port not in [993, 465]:
        errors.append(f"Port {port} is not a standard SSL IMAP port (993, 465)")
    elif not use_ssl and port not in [143, 110]:
        errors.append(f"Port {port} is not a standard IMAP port (143, 110)")
    
    return errors


def validate_mailbox_settings(name: str, delimiter: str = '/') -> List[str]:
    """
    Validate mailbox settings.
    
    Args:
        name: Mailbox name
        delimiter: Hierarchy delimiter
        
    Returns:
        List of validation errors
    """
    errors = []
    
    try:
        validate_folder_name(name)
    except Exception as e:
        errors.append(f"Invalid folder name: {e}")
    
    if len(delimiter) != 1:
        errors.append("Delimiter must be a single character")
    
    return errors


def validate_attachment_settings(max_size: int, allowed_extensions: List[str]) -> List[str]:
    """
    Validate attachment settings.
    
    Args:
        max_size: Maximum attachment size in bytes
        allowed_extensions: List of allowed file extensions
        
    Returns:
        List of validation errors
    """
    errors = []
    
    try:
        validate_file_size(0, max_size)
    except Exception as e:
        errors.append(f"Invalid max size: {e}")
    
    if not allowed_extensions:
        errors.append("No allowed extensions specified")
    
    for ext in allowed_extensions:
        if not ext.startswith('.'):
            errors.append(f"Extension '{ext}' should start with a dot")
    
    return errors


def get_system_info() -> dict:
    """
    Get system information for debugging.
    
    Returns:
        Dictionary with system information
    """
    import platform
    import sys
    import django
    
    info = {
        'python_version': sys.version,
        'django_version': django.VERSION,
        'platform': platform.platform(),
        'hostname': socket.gethostname(),
        'debug': settings.DEBUG,
        'database_engine': settings.DATABASES.get('default', {}).get('ENGINE', 'Unknown'),
        'installed_apps': len(settings.INSTALLED_APPS),
        'middleware_count': len(getattr(settings, 'MIDDLEWARE', [])),
        'timezone': settings.TIME_ZONE,
        'language_code': settings.LANGUAGE_CODE,
        'use_tz': settings.USE_TZ,
        'use_i18n': settings.USE_I18N,
    }
    
    # Add sage_mailbox specific info
    info.update({
        'sage_mailbox_sync_batch_size': getattr(settings, 'SAGE_MAILBOX_SYNC_BATCH_SIZE', 50),
        'sage_mailbox_max_attachment_size': getattr(settings, 'SAGE_MAILBOX_MAX_ATTACHMENT_SIZE', 25 * 1024 * 1024),
        'sage_mailbox_cleanup_days': getattr(settings, 'SAGE_MAILBOX_CLEANUP_DAYS', 30),
        'sage_mailbox_encrypt_passwords': getattr(settings, 'SAGE_MAILBOX_ENCRYPT_PASSWORDS', True),
        'sage_mailbox_use_json_forms': getattr(settings, 'SAGE_MAILBOX_USE_JSON_FORMS', True),
    })
    
    return info 