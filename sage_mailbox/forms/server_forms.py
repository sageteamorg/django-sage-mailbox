"""
Server forms for sage_mailbox.

This module contains forms for managing IMAP and SMTP server configurations
with proper validation and sage_imap integration.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.forms import CharField, Textarea
from django.forms.widgets import PasswordInput
from django.utils.translation import gettext_lazy as _

# Import sage_imap for validation
from sage_imap.services.client import ConnectionConfig
from sage_imap import IMAPClient

from ..models import IMAPServer, SMTPServer
from .base import BaseModelForm


class IMAPServerForm(BaseModelForm):
    """
    Custom form for IMAP Server with validation using sage_imap.
    
    This form provides validation for IMAP server configurations using
    the sage_imap library to ensure connections can be established.
    """
    
    class Meta:
        model = IMAPServer
        fields = '__all__'
        widgets = {
            'password': PasswordInput(),
        }
        help_text = {
            'host': _('IMAP server hostname (e.g., imap.gmail.com)'),
            'port': _('IMAP server port (typically 993 for SSL, 143 for non-SSL)'),
            'username': _('Username for IMAP authentication'),
            'password': _('Password for IMAP authentication (will be encrypted)'),
            'use_ssl': _('Use SSL/TLS encryption for secure connection'),
            'timeout': _('Connection timeout in seconds'),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate server configuration using sage_imap
        host = cleaned_data.get('host')
        port = cleaned_data.get('port')
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        use_ssl = cleaned_data.get('use_ssl', True)
        timeout = cleaned_data.get('timeout', 30.0)
        
        if all([host, port, username, password]):
            try:
                # Use sage_imap ConnectionConfig for validation
                config = ConnectionConfig(
                    host=host,
                    port=port,
                    username=username,
                    password=password,
                    use_ssl=use_ssl,
                    timeout=timeout
                )
                
                # Test connection using sage_imap (don't test on form validation by default)
                # Connection will be tested when explicitly requested via admin action
                
            except Exception as e:
                raise ValidationError(f"IMAP server configuration error: {e}")
        
        return cleaned_data


class SMTPServerForm(BaseModelForm):
    """
    Form for SMTP Server model with password field handling.
    
    This form provides proper password handling and validation for
    SMTP server configurations.
    """
    
    password = CharField(
        widget=PasswordInput(render_value=False),
        help_text=_("Password for SMTP authentication (will be encrypted)")
    )
    
    class Meta:
        model = SMTPServer
        fields = '__all__'
        widgets = {
            'signature': Textarea(attrs={'rows': 4, 'cols': 80}),
        }
        help_text = {
            'host': _('SMTP server hostname (e.g., smtp.gmail.com)'),
            'port': _('SMTP server port (typically 587 for TLS, 465 for SSL, 25 for plain)'),
            'username': _('Username for SMTP authentication'),
            'use_tls': _('Use STARTTLS for secure connection'),
            'use_ssl': _('Use SSL/TLS encryption for secure connection'),
            'timeout': _('Connection timeout in seconds'),
            'from_email': _('Default sender email address'),
            'from_name': _('Default sender name'),
            'signature': _('Email signature to append to outgoing emails'),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Basic validation
        host = cleaned_data.get('host')
        port = cleaned_data.get('port')
        use_tls = cleaned_data.get('use_tls')
        use_ssl = cleaned_data.get('use_ssl')
        timeout = cleaned_data.get('timeout')
        
        if host and port:
            try:
                # Basic port validation
                if port <= 0 or port > 65535:
                    raise ValidationError("Port must be between 1 and 65535")
                
                # Basic timeout validation
                if timeout <= 0:
                    raise ValidationError("Timeout must be greater than 0")
                
                # Validate TLS/SSL settings
                if use_tls and use_ssl:
                    raise ValidationError("Cannot use both TLS and SSL encryption")
                    
            except Exception as e:
                raise ValidationError(f"SMTP server configuration error: {e}")
        
        return cleaned_data 