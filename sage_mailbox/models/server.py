"""
Server configuration models for sage_mailbox.

This module contains models for storing IMAP and SMTP server configurations.
These models handle connection details and authentication for email servers.
"""

import uuid
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from .mixins import TimestampMixin


class IMAPServer(TimestampMixin):
    """
    IMAP server configuration for receiving emails.
    
    This model stores all the necessary information to connect to an IMAP server
    and retrieve emails. IMAP (Internet Message Access Protocol) is used for
    reading emails from a mail server.
    
    Each configuration belongs to a specific user and can be activated/deactivated
    as needed. Passwords are automatically encrypted for security.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="Unique identifier for IMAP server configuration"
    )
    
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Server name"),
        help_text=_("Give this server a memorable name (e.g., 'My Gmail Account', 'Work Email')"),
        db_comment="Human-readable name for the server"
    )
    
    host = models.CharField(
        max_length=255,
        verbose_name=_("IMAP host"),
        help_text=_("The server address (e.g., 'imap.gmail.com' for Gmail, 'outlook.office365.com' for Outlook)"),
        db_comment="IMAP server hostname or IP address"
    )
    
    port = models.PositiveIntegerField(
        default=993,
        verbose_name=_("Port"),
        help_text=_("The port number (993 for secure connections, 143 for non-secure)"),
        db_comment="Port number for IMAP connection"
    )
    
    username = models.CharField(
        max_length=255,
        verbose_name=_("Username"),
        help_text=_("Your email address or username for logging into the email server"),
        db_comment="Username for IMAP server authentication"
    )
    
    password = models.CharField(
        max_length=255,
        verbose_name=_("Password"),
        help_text=_("Your email password or app-specific password (will be encrypted automatically)"),
        db_comment="Encrypted password for IMAP server authentication"
    )
    
    use_ssl = models.BooleanField(
        default=True,
        verbose_name=_("Use SSL"),
        help_text=_("Enable for secure connections (recommended). Most email providers require this."),
        db_comment="Whether SSL encryption is enabled"
    )
    
    timeout = models.FloatField(
        default=30.0,
        verbose_name=_("Timeout"),
        help_text=_("How long to wait for server response (in seconds). 30 seconds is usually good."),
        db_comment="Connection timeout in seconds"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
        help_text=_("Uncheck to temporarily disable this server configuration without deleting it"),
        db_comment="Whether server configuration is active"
    )
    
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="imap_servers",
        verbose_name=_("Owner"),
        help_text=_("The user account that owns this email server configuration"),
        db_comment="User who owns this server configuration"
    )
    
    class Meta:
        db_table = "sage_imap_server"
        verbose_name = _("IMAP Server")
        verbose_name_plural = _("IMAP Servers")
        ordering = ["name"]
    
    def __str__(self):
        return f"{self.name} ({self.host}:{self.port})"
    
    def clean(self):
        if self.port <= 0 or self.port > 65535:
            raise ValidationError(_("Port must be between 1 and 65535"))
        
        if self.timeout <= 0:
            raise ValidationError(_("Timeout must be greater than 0"))
    
    def save(self, *args, **kwargs):
        """Override save to encrypt password."""
        from ..security.encryption import password_encryption
        
        # Only encrypt if password was changed and is not already encrypted
        if self.password and not self._is_password_encrypted():
            self.password = password_encryption.encrypt_password(self.password)
        
        super().save(*args, **kwargs)
    
    def _is_password_encrypted(self):
        """Check if password is already encrypted."""
        if not self.password:
            return False
            
        try:
            # Check if it's encrypted by trying to decrypt it
            from ..security.encryption import password_encryption
            password_encryption.decrypt_password(self.password)
            return True
        except Exception:
            # If decryption fails, it's not encrypted
            return False
    
    def get_decrypted_password(self):
        """Get the decrypted password for use in connections."""
        from ..security.encryption import password_encryption
        
        if not self.password:
            return ""
        
        # If password doesn't look encrypted, return as-is (for migration purposes)
        if not self._is_password_encrypted():
            return self.password
        
        try:
            return password_encryption.decrypt_password(self.password)
        except Exception as e:
            # If decryption fails, assume it's plain text (for migration)
            return self.password


class SMTPServer(TimestampMixin):
    """
    SMTP server configuration for sending emails.
    
    This model stores all the necessary information to connect to an SMTP server
    and send emails. SMTP (Simple Mail Transfer Protocol) is used for sending
    emails through a mail server.
    
    Each configuration belongs to a specific user and includes settings for
    the sender's information and email signature. Passwords are automatically
    encrypted for security.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="Unique identifier for SMTP server configuration"
    )
    
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Server name"),
        help_text=_("Give this server a memorable name (e.g., 'My Gmail SMTP', 'Work Email Outgoing')"),
        db_comment="Human-readable name for the server"
    )
    
    host = models.CharField(
        max_length=255,
        verbose_name=_("SMTP host"),
        help_text=_("The server address (e.g., 'smtp.gmail.com' for Gmail, 'smtp.office365.com' for Outlook)"),
        db_comment="SMTP server hostname or IP address"
    )
    
    port = models.PositiveIntegerField(
        default=587,
        verbose_name=_("Port"),
        help_text=_("The port number (587 for TLS, 465 for SSL, 25 for non-secure)"),
        db_comment="Port number for SMTP connection"
    )
    
    username = models.CharField(
        max_length=255,
        verbose_name=_("Username"),
        help_text=_("Your email address or username for logging into the email server"),
        db_comment="Username for SMTP server authentication"
    )
    
    password = models.CharField(
        max_length=255,
        verbose_name=_("Password"),
        help_text=_("Your email password or app-specific password (will be encrypted automatically)"),
        db_comment="Encrypted password for SMTP server authentication"
    )
    
    use_tls = models.BooleanField(
        default=True,
        verbose_name=_("Use TLS"),
        help_text=_("Enable TLS encryption for secure connections (recommended for port 587)"),
        db_comment="Whether TLS encryption is enabled"
    )
    
    use_ssl = models.BooleanField(
        default=False,
        verbose_name=_("Use SSL"),
        help_text=_("Enable SSL encryption for secure connections (recommended for port 465)"),
        db_comment="Whether SSL encryption is enabled"
    )
    
    timeout = models.FloatField(
        default=30.0,
        verbose_name=_("Timeout"),
        help_text=_("How long to wait for server response (in seconds). 30 seconds is usually good."),
        db_comment="Connection timeout in seconds"
    )
    
    from_email = models.EmailField(
        verbose_name=_("From email"),
        help_text=_("The email address that will appear as the sender in outgoing emails"),
        db_comment="Default sender email address"
    )
    
    from_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("From name"),
        help_text=_("The name that will appear as the sender (e.g., 'John Doe', 'Company Support')"),
        db_comment="Default sender name"
    )
    
    signature = models.TextField(
        blank=True,
        verbose_name=_("Email signature"),
        help_text=_("Text to automatically add at the end of all emails (e.g., contact info, company details)"),
        db_comment="Default email signature"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
        help_text=_("Uncheck to temporarily disable this server configuration without deleting it"),
        db_comment="Whether server configuration is active"
    )
    
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="smtp_servers",
        verbose_name=_("Owner"),
        help_text=_("The user account that owns this email server configuration"),
        db_comment="User who owns this server configuration"
    )
    
    class Meta:
        db_table = "sage_smtp_server"
        verbose_name = _("SMTP Server")
        verbose_name_plural = _("SMTP Servers")
        ordering = ["name"]
    
    def __str__(self):
        return f"{self.name} ({self.host}:{self.port})"
    
    def clean(self):
        if self.port <= 0 or self.port > 65535:
            raise ValidationError(_("Port must be between 1 and 65535"))
        
        if self.timeout <= 0:
            raise ValidationError(_("Timeout must be greater than 0"))
        
        if self.use_tls and self.use_ssl:
            raise ValidationError(_("Cannot use both TLS and SSL encryption"))
    
    def save(self, *args, **kwargs):
        """Override save to encrypt password."""
        from ..security.encryption import password_encryption
        
        # Only encrypt if password was changed and is not already encrypted
        if self.password and not self._is_password_encrypted():
            self.password = password_encryption.encrypt_password(self.password)
        
        super().save(*args, **kwargs)
    
    def _is_password_encrypted(self):
        """Check if password is already encrypted."""
        if not self.password:
            return False
            
        try:
            # Check if it's encrypted by trying to decrypt it
            from ..security.encryption import password_encryption
            password_encryption.decrypt_password(self.password)
            return True
        except Exception:
            # If decryption fails, it's not encrypted
            return False
    
    def get_decrypted_password(self):
        """Get the decrypted password for use in connections."""
        from ..security.encryption import password_encryption
        
        if not self.password:
            return ""
        
        # If password doesn't look encrypted, return as-is (for migration purposes)
        if not self._is_password_encrypted():
            return self.password
        
        try:
            return password_encryption.decrypt_password(self.password)
        except Exception as e:
            # If decryption fails, assume it's plain text (for migration)
            return self.password 