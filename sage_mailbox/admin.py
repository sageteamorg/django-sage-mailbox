"""
Django admin configuration for sage_mailbox models.

This module provides a comprehensive admin interface for managing
IMAP servers, mailboxes, emails, and attachments with professional styling
and advanced features using full sage_imap capabilities.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.contrib.admin.views.main import ChangeList
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count, Sum, Q
from django.forms import ModelForm, CharField, Textarea
from django.forms.widgets import PasswordInput
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html, mark_safe
from django.utils.safestring import SafeString
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import now
from django.contrib import messages
from django.contrib.admin.utils import unquote

# Import sage_imap services and models for admin functions
from sage_imap import IMAPClient, IMAPFolderService
from sage_imap.services.client import ConnectionConfig
from sage_imap.services.mailbox import IMAPMailboxService, MailboxStatistics
from sage_imap.helpers.enums import Flag
from sage_imap.exceptions import IMAPConnectionError, IMAPAuthenticationError

from .models import IMAPServer, SMTPServer, EmailTemplate, Mailbox, Email, Attachment, EmailFlag
from .utils import format_file_size, EmailUtils, DateUtils, MailboxUtils
from .forms import EmailComposeForm

# Try to import django-jsonform if available
try:
    from django_jsonform.widgets import JSONFormWidget
    HAS_JSONFORM = True
except ImportError:
    HAS_JSONFORM = False

import logging
logger = logging.getLogger(__name__)


class BaseModelAdmin(ModelAdmin):
    """Base admin class with common configurations."""
    
    save_on_top = True
    list_per_page = 50
    
    def get_readonly_fields(self, request, obj=None):
        """Add created_at and updated_at to readonly fields."""
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if hasattr(self.model, 'created_at'):
            readonly_fields.append('created_at')
        if hasattr(self.model, 'updated_at'):
            readonly_fields.append('updated_at')
        return readonly_fields


class IMAPServerForm(ModelForm):
    """Custom form for IMAP Server with validation using sage_imap."""
    
    class Meta:
        model = IMAPServer
        fields = '__all__'
        widgets = {
            'password': PasswordInput(),
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


@admin.register(IMAPServer)
class IMAPServerAdmin(BaseModelAdmin):
    """Admin interface for IMAP Server model with full sage_imap integration."""
    
    form = IMAPServerForm
    list_display = [
        'name', 'host', 'port', 'username', 'owner', 'is_active',
        'mailbox_count', 'total_emails', 'connection_status', 'created_at'
    ]
    list_display_links = ['name', 'host']
    list_filter = ['is_active', 'use_ssl', 'port', 'created_at', 'owner']
    search_fields = ['name', 'host', 'username', 'owner__username']
    readonly_fields = ['created_at', 'updated_at', 'connection_status']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'owner', 'is_active')
        }),
        (_('Connection Settings'), {
            'fields': ('host', 'port', 'use_ssl', 'timeout')
        }),
        (_('Authentication'), {
            'fields': ('username', 'password'),
            'classes': ('collapse',)
        }),
        (_('Status'), {
            'fields': ('connection_status',),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'test_connection_sage_imap', 'sync_mailboxes_sage_imap', 
        'get_server_capabilities', 'activate_servers', 'deactivate_servers'
    ]
    
    def get_queryset(self, request):
        """Add annotations to queryset."""
        return super().get_queryset(request).annotate(
            mailbox_count=Count('mailboxes'),
            total_emails=Count('mailboxes__emails')
        ).select_related('owner')
    
    def mailbox_count(self, obj):
        """Display mailbox count."""
        return obj.mailbox_count
    mailbox_count.short_description = _('Mailboxes')
    mailbox_count.admin_order_field = 'mailbox_count'
    
    def total_emails(self, obj):
        """Display total email count."""
        return obj.total_emails
    total_emails.short_description = _('Total Emails')
    total_emails.admin_order_field = 'total_emails'
    
    def connection_status(self, obj):
        """Display connection status using sage_imap."""
        try:
            config = ConnectionConfig(
                host=obj.host,
                port=obj.port,
                username=obj.username,
                password=obj.get_decrypted_password(),
                use_ssl=obj.use_ssl,
                timeout=obj.timeout
            )
            
            # Quick connection test
            with IMAPClient.from_config(config) as client:
                if client.is_connected():
                    return format_html('<span style="color: green;">✓ Connected</span>')
                else:
                    return format_html('<span style="color: red;">✗ Disconnected</span>')
        except Exception as e:
            return format_html('<span style="color: red;">✗ Error: {}</span>', str(e)[:50])
    
    connection_status.short_description = _('Connection Status')
    
    def test_connection_sage_imap(self, request, queryset):
        """Test connection to selected servers using sage_imap."""
        success_count = 0
        for server in queryset:
            try:
                config = ConnectionConfig(
                    host=server.host,
                    port=server.port,
                    username=server.username,
                    password=server.get_decrypted_password(),
                    use_ssl=server.use_ssl,
                    timeout=server.timeout
                )
                
                with IMAPClient.from_config(config) as client:
                    if client.is_connected():
                        # Get server capabilities
                        capabilities = client.get_capabilities()
                        success_count += 1
                        messages.success(
                            request, 
                            f"✓ {server.name}: Connected successfully. Capabilities: {', '.join(capabilities[:5])}"
                        )
                    else:
                        messages.error(request, f"✗ {server.name}: Connection failed")
                        
            except IMAPConnectionError as e:
                messages.error(request, f"✗ {server.name}: Connection error - {e}")
            except IMAPAuthenticationError as e:
                messages.error(request, f"✗ {server.name}: Authentication error - {e}")
            except Exception as e:
                messages.error(request, f"✗ {server.name}: Unexpected error - {e}")
        
        if success_count > 0:
            messages.success(request, f"Successfully connected to {success_count} server(s)")
    
    test_connection_sage_imap.short_description = _('Test connection (sage_imap)')
    
    def sync_mailboxes_sage_imap(self, request, queryset):
        """Sync mailboxes for selected servers using repository method."""
        for server in queryset:
            try:
                # Use the repository method for syncing mailboxes
                mailboxes = Mailbox.objects.sync_mailboxes_from_server(server)
                messages.success(request, f"✓ {server.name}: Synced {len(mailboxes)} mailboxes")
            except Exception as e:
                messages.error(request, f"✗ {server.name}: Sync failed - {e}")
    
    sync_mailboxes_sage_imap.short_description = _('Sync mailboxes (repository)')
    
    def get_server_capabilities(self, request, queryset):
        """Get server capabilities using sage_imap."""
        for server in queryset:
            try:
                config = ConnectionConfig(
                    host=server.host,
                    port=server.port,
                    username=server.username,
                    password=server.get_decrypted_password(),
                    use_ssl=server.use_ssl,
                    timeout=server.timeout
                )
                
                with IMAPClient.from_config(config) as client:
                    capabilities = client.get_capabilities()
                    messages.info(
                        request, 
                        f"📋 {server.name}: Capabilities - {', '.join(capabilities)}"
                    )
                    
            except Exception as e:
                messages.error(request, f"✗ {server.name}: Failed to get capabilities - {e}")
    
    get_server_capabilities.short_description = _('Get server capabilities')
    
    def activate_servers(self, request, queryset):
        """Activate selected servers."""
        updated = queryset.update(is_active=True)
        messages.success(request, f"Activated {updated} server(s)")
    
    activate_servers.short_description = _('Activate servers')
    
    def deactivate_servers(self, request, queryset):
        """Deactivate selected servers."""
        updated = queryset.update(is_active=False)
        messages.success(request, f"Deactivated {updated} server(s)")
    
    deactivate_servers.short_description = _('Deactivate servers')


class SMTPServerForm(ModelForm):
    """Form for SMTP Server model with password field handling."""
    
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


@admin.register(SMTPServer)
class SMTPServerAdmin(BaseModelAdmin):
    """Admin interface for SMTP Server model with email sending capabilities."""
    
    form = SMTPServerForm
    list_display = [
        'name', 'host', 'port', 'from_email', 'from_name', 'owner', 'is_active',
        'use_tls', 'use_ssl', 'connection_status', 'created_at'
    ]
    list_display_links = ['name', 'host']
    list_filter = ['is_active', 'use_tls', 'use_ssl', 'port', 'created_at', 'owner']
    search_fields = ['name', 'host', 'username', 'from_email', 'from_name', 'owner__username']
    readonly_fields = ['created_at', 'updated_at', 'connection_status']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'owner', 'is_active')
        }),
        (_('Connection Settings'), {
            'fields': ('host', 'port', 'use_tls', 'use_ssl', 'timeout')
        }),
        (_('Authentication'), {
            'fields': ('username', 'password'),
            'classes': ('collapse',)
        }),
        (_('Email Settings'), {
            'fields': ('from_email', 'from_name', 'signature'),
            'description': 'Configure default sender information and signature'
        }),
        (_('Status'), {
            'fields': ('connection_status',),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'test_connection_smtp', 'send_test_email', 'activate_servers', 'deactivate_servers'
    ]
    
    def connection_status(self, obj):
        """Display SMTP connection status."""
        try:
            import smtplib
            
            # Create SMTP connection
            if obj.use_ssl:
                server = smtplib.SMTP_SSL(obj.host, obj.port, timeout=obj.timeout)
            else:
                server = smtplib.SMTP(obj.host, obj.port, timeout=obj.timeout)
                if obj.use_tls:
                    server.starttls()
            
            # Test authentication
            if obj.username and obj.password:
                server.login(obj.username, obj.get_decrypted_password())
            
            server.quit()
            return format_html('<span style="color: green;">✓ Connected</span>')
            
        except Exception as e:
            return format_html('<span style="color: red;">✗ Error: {}</span>', str(e)[:50])
    
    connection_status.short_description = _('Connection Status')
    
    def test_connection_smtp(self, request, queryset):
        """Test SMTP connection for selected servers."""
        success_count = 0
        for server in queryset:
            try:
                import smtplib
                
                if server.use_ssl:
                    smtp_server = smtplib.SMTP_SSL(server.host, server.port, timeout=server.timeout)
                else:
                    smtp_server = smtplib.SMTP(server.host, server.port, timeout=server.timeout)
                    if server.use_tls:
                        smtp_server.starttls()
                
                if server.username and server.password:
                    smtp_server.login(server.username, server.get_decrypted_password())
                
                smtp_server.quit()
                success_count += 1
                
            except Exception as e:
                messages.error(request, f"Connection failed for {server.name}: {str(e)}")
        
        if success_count > 0:
            messages.success(request, f"Successfully connected to {success_count} SMTP server(s)")
    
    test_connection_smtp.short_description = _('Test SMTP connection')
    
    def send_test_email(self, request, queryset):
        """Send test email using selected SMTP servers."""
        if not request.user.email:
            messages.error(request, "Your user account must have an email address to send test emails")
            return
        
        success_count = 0
        for server in queryset:
            try:
                from .services.email_service import EmailSendingService
                
                service = EmailSendingService(smtp_server=server)
                service.send_email(
                    to_addresses=[request.user.email],
                    subject="Test Email from Django-Sage-Mailbox",
                    body_html="<h2>Test Email</h2><p>This is a test email sent from Django-Sage-Mailbox admin interface.</p>",
                    body_plain="Test Email\n\nThis is a test email sent from Django-Sage-Mailbox admin interface.",
                    save_to_sent=False  # Don't save test emails to sent folder
                )
                success_count += 1
                
            except Exception as e:
                messages.error(request, f"Failed to send test email from {server.name}: {str(e)}")
        
        if success_count > 0:
            messages.success(request, f"Successfully sent test email from {success_count} SMTP server(s)")
    
    send_test_email.short_description = _('Send test email')
    
    def activate_servers(self, request, queryset):
        """Activate selected servers."""
        updated = queryset.update(is_active=True)
        messages.success(request, f"Activated {updated} SMTP server(s)")
    
    activate_servers.short_description = _('Activate servers')
    
    def deactivate_servers(self, request, queryset):
        """Deactivate selected servers."""
        updated = queryset.update(is_active=False)
        messages.success(request, f"Deactivated {updated} SMTP server(s)")
    
    deactivate_servers.short_description = _('Deactivate servers')


@admin.register(EmailTemplate)
class EmailTemplateAdmin(BaseModelAdmin):
    """Admin interface for Email Template model."""
    
    list_display = [
        'name', 'subject', 'owner', 'is_active', 'created_at', 'updated_at'
    ]
    list_display_links = ['name', 'subject']
    list_filter = ['is_active', 'created_at', 'owner']
    search_fields = ['name', 'subject', 'body_html', 'body_plain', 'owner__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'owner', 'is_active')
        }),
        (_('Email Content'), {
            'fields': ('subject', 'body_html', 'body_plain'),
            'description': 'Configure the email template content'
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_templates', 'deactivate_templates', 'duplicate_templates']
    
    def get_form(self, request, obj=None, **kwargs):
        """Customize form for rich text editing."""
        form = super().get_form(request, obj, **kwargs)
        
        # Add rich text editor for HTML body
        form.base_fields['body_html'].widget = Textarea(attrs={
            'rows': 20,
            'cols': 100,
            'class': 'vLargeTextField',
            'style': 'font-family: monospace;'
        })
        
        form.base_fields['body_plain'].widget = Textarea(attrs={
            'rows': 15,
            'cols': 100,
            'class': 'vLargeTextField'
        })
        
        return form
    
    def activate_templates(self, request, queryset):
        """Activate selected templates."""
        updated = queryset.update(is_active=True)
        messages.success(request, f"Activated {updated} template(s)")
    
    activate_templates.short_description = _('Activate templates')
    
    def deactivate_templates(self, request, queryset):
        """Deactivate selected templates."""
        updated = queryset.update(is_active=False)
        messages.success(request, f"Deactivated {updated} template(s)")
    
    deactivate_templates.short_description = _('Deactivate templates')
    
    def duplicate_templates(self, request, queryset):
        """Duplicate selected templates."""
        duplicated_count = 0
        for template in queryset:
            template.pk = None
            template.name = f"{template.name} (Copy)"
            template.save()
            duplicated_count += 1
        
        messages.success(request, f"Duplicated {duplicated_count} template(s)")
    
    duplicate_templates.short_description = _('Duplicate templates')


@admin.register(Mailbox)
class MailboxAdmin(BaseModelAdmin):
    """Admin interface for Mailbox model with sage_imap integration."""
    
    list_display = [
        'name', 'display_name', 'server', 'is_default', 'message_count',
        'unseen_count', 'last_sync', 'mailbox_icon'
    ]
    list_display_links = ['name', 'display_name']
    list_filter = ['is_default', 'server', 'last_sync', 'server__owner']
    search_fields = ['name', 'display_name', 'server__name']
    readonly_fields = ['created_at', 'updated_at', 'uidvalidity', 'uidnext']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('server', 'name', 'display_name', 'is_default')
        }),
        (_('Hierarchy'), {
            'fields': ('parent', 'delimiter')
        }),
        (_('Statistics'), {
            'fields': ('message_count', 'unseen_count', 'last_sync'),
            'classes': ('collapse',)
        }),
        (_('IMAP Information'), {
            'fields': ('uidvalidity', 'uidnext'),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'sync_emails_sage_imap', 'full_sync_sage_imap', 'update_stats_sage_imap',
        'get_mailbox_info', 'cleanup_deleted_emails'
    ]
    
    def get_queryset(self, request):
        """Add optimizations to queryset."""
        return super().get_queryset(request).select_related('server', 'parent')
    
    def mailbox_icon(self, obj):
        """Display mailbox icon."""
        icon_class = MailboxUtils.get_mailbox_icon(obj.name)
        return format_html('<i class="fa {}"></i>', icon_class)
    
    mailbox_icon.short_description = _('Icon')
    
    def sync_emails_sage_imap(self, request, queryset):
        """Sync emails for selected mailboxes using repository method."""
        for mailbox in queryset:
            try:
                # Use the repository method for syncing emails
                created, updated = Email.objects.sync_emails_from_server(
                    mailbox, full_sync=False, limit=100
                )
                messages.success(request, f"✓ {mailbox.name}: Synced {created} new emails")
            except Exception as e:
                messages.error(request, f"✗ {mailbox.name}: Sync failed - {e}")
    
    sync_emails_sage_imap.short_description = _('Sync new emails (repository)')
    
    def full_sync_sage_imap(self, request, queryset):
        """Full sync emails for selected mailboxes using sage_imap."""
        for mailbox in queryset:
            try:
                created, updated = Email.objects.sync_emails_from_server(
                    mailbox, full_sync=True, limit=1000
                )
                messages.success(
                    request,
                    f"✓ {mailbox.name}: Full sync completed - {created} created, {updated} updated"
                )
            except Exception as e:
                messages.error(request, f"✗ {mailbox.name}: Full sync failed - {e}")
    
    full_sync_sage_imap.short_description = _('Full sync emails (sage_imap)')
    
    def update_stats_sage_imap(self, request, queryset):
        """Update statistics for selected mailboxes using repository method."""
        for mailbox in queryset:
            try:
                # Use the repository method for updating mailbox stats
                stats = Mailbox.objects.update_mailbox_stats(mailbox)
                messages.success(request, f"✓ {mailbox.name}: Updated stats successfully")
            except Exception as e:
                messages.error(request, f"✗ {mailbox.name}: Stats update failed - {e}")
    
    update_stats_sage_imap.short_description = _('Update statistics (repository)')
    
    def get_mailbox_info(self, request, queryset):
        """Get detailed mailbox information using sage_imap."""
        for mailbox in queryset:
            try:
                config = ConnectionConfig(
                    host=mailbox.server.host,
                    port=mailbox.server.port,
                    username=mailbox.server.username,
                    password=mailbox.server.get_decrypted_password(),
                    use_ssl=mailbox.server.use_ssl,
                    timeout=mailbox.server.timeout
                )
                
                with IMAPClient.from_config(config) as client:
                    folder_service = IMAPFolderService(client)
                    folder_info = folder_service.get_folder_info(mailbox.name)
                    
                    info_text = f"📂 {mailbox.name}: "
                    info_text += f"Selectable: {folder_info.selectable}, "
                    info_text += f"Has Children: {folder_info.has_children}, "
                    info_text += f"Attributes: {', '.join(folder_info.attributes)}"
                    
                    messages.info(request, info_text)
                    
            except Exception as e:
                messages.error(request, f"✗ {mailbox.name}: Failed to get info - {e}")
    
    get_mailbox_info.short_description = _('Get mailbox info (sage_imap)')
    
    def cleanup_deleted_emails(self, request, queryset):
        """Cleanup emails deleted on server using repository method."""
        for mailbox in queryset:
            try:
                # Check if the repository has a cleanup_deleted_emails method
                if hasattr(Email.objects, 'cleanup_deleted_emails'):
                    deleted_count = Email.objects.cleanup_deleted_emails(mailbox)
                    if deleted_count > 0:
                        messages.success(request, f"✓ {mailbox.name}: Cleaned up {deleted_count} deleted emails")
                    else:
                        messages.info(request, f"ℹ {mailbox.name}: No deleted emails to cleanup")
                else:
                    messages.info(request, f"ℹ {mailbox.name}: Cleanup method not available")
                    
            except Exception as e:
                messages.error(request, f"✗ {mailbox.name}: Cleanup failed - {e}")
    
    cleanup_deleted_emails.short_description = _('Cleanup deleted emails (repository)')


class EmailForm(ModelForm):
    """Custom form for Email model."""
    
    class Meta:
        model = Email
        fields = '__all__'
        widgets = {
            'headers': Textarea(attrs={'rows': 10}),
            'plain_body': Textarea(attrs={'rows': 15}),
            'html_body': Textarea(attrs={'rows': 15}),
        }


@admin.register(Email)
class EmailAdmin(BaseModelAdmin):
    """Admin interface for Email model with sage_imap integration."""
    
    form = EmailForm
    list_display = [
        'subject_truncated', 'from_address', 'mailbox', 'date',
        'size_formatted', 'flag_indicators', 'attachment_count',
        'send_status', 'priority', 'is_outgoing'
    ]
    list_display_links = ['subject_truncated']
    list_filter = [
        'mailbox', 'is_seen', 'is_flagged', 'is_answered', 'is_deleted',
        'is_in_trash', 'date', 'mailbox__server', 'send_status', 'priority',
        'is_outgoing', 'smtp_server'
    ]
    search_fields = [
        'subject', 'from_address', 'message_id', 'plain_body',
        'to_addresses', 'cc_addresses'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'uid', 'size', 'headers_formatted',
        'raw_content_preview', 'message_id', 'sent_at', 'send_attempts'
    ]
    date_hierarchy = 'date'
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('mailbox', 'uid', 'message_id', 'subject', 'date')
        }),
        (_('Addresses'), {
            'fields': ('from_address', 'from_name', 'to_addresses', 'cc_addresses', 'bcc_addresses', 'reply_to')
        }),
        (_('Content'), {
            'fields': ('plain_body', 'html_body', 'size'),
            'classes': ('collapse',)
        }),
        (_('Composition & Sending'), {
            'fields': ('smtp_server', 'template', 'priority', 'is_outgoing', 'send_status', 'sent_at', 'send_attempts', 'send_error'),
            'classes': ('collapse',)
        }),
        (_('Email Threading'), {
            'fields': ('in_reply_to', 'references'),
            'classes': ('collapse',)
        }),
        (_('Flags'), {
            'fields': ('is_seen', 'is_answered', 'is_flagged', 'is_deleted', 'is_draft', 'is_recent')
        }),
        (_('Trash Management'), {
            'fields': ('is_in_trash', 'original_mailbox', 'deleted_at'),
            'classes': ('collapse',)
        }),
        (_('Headers'), {
            'fields': ('headers_formatted',),
            'classes': ('collapse',)
        }),
        (_('Raw Content'), {
            'fields': ('raw_content_preview',),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'mark_as_read_sage_imap', 'mark_as_unread_sage_imap', 
        'mark_as_flagged_sage_imap', 'mark_as_unflagged_sage_imap',
        'move_to_trash_sage_imap', 'restore_from_trash_sage_imap', 
        'permanent_delete_sage_imap', 'download_as_eml_sage_imap',
        'sync_flags_sage_imap', 'get_email_flags'
    ]

    def get_urls(self):
        """Add custom URLs for email composition."""
        urls = super().get_urls()
        custom_urls = [
            path('compose/', self.admin_site.admin_view(self.compose_email_view), name='sage_mailbox_email_compose'),
            path('<path:object_id>/reply/', self.admin_site.admin_view(self.reply_email_view), name='sage_mailbox_email_reply'),
            path('<path:object_id>/forward/', self.admin_site.admin_view(self.forward_email_view), name='sage_mailbox_email_forward'),
        ]
        return custom_urls + urls

    def has_add_permission(self, request):
        """Disable regular add functionality - emails should only be composed or synced."""
        return False

    def changelist_view(self, request, extra_context=None):
        """Add compose button to changelist view."""
        extra_context = extra_context or {}
        extra_context['compose_url'] = reverse('admin:sage_mailbox_email_compose')
        return super().changelist_view(request, extra_context)

    def compose_email_view(self, request):
        """Compose and send new email."""
        if request.method == 'POST':
            form = EmailComposeForm(request.user, request.POST)
            if form.is_valid():
                return self._handle_email_composition_form(request, 'compose', form)
        else:
            form = EmailComposeForm(request.user)
        
        # Show composition form
        return render(request, 'admin/sage_mailbox/compose_email.html', {
            'title': 'Compose New Email',
            'action': 'compose',
            'form': form,
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
        })

    def reply_email_view(self, request, object_id):
        """Reply to selected email."""
        email = get_object_or_404(Email, pk=unquote(object_id))
        
        if request.method == 'POST':
            form = EmailComposeForm(request.user, request.POST)
            if form.is_valid():
                return self._handle_email_composition_form(request, 'reply', form, email)
        else:
            # Pre-populate form for reply
            initial_data = {
                'to_addresses': email.from_address,
                'subject': f'Re: {email.subject}',
            }
            form = EmailComposeForm(request.user, initial=initial_data)
        
        # Show reply form
        return render(request, 'admin/sage_mailbox/compose_email.html', {
            'title': f'Reply to: {email.subject}',
            'action': 'reply',
            'original_email': email,
            'form': form,
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
        })

    def forward_email_view(self, request, object_id):
        """Forward selected email."""
        email = get_object_or_404(Email, pk=unquote(object_id))
        
        if request.method == 'POST':
            form = EmailComposeForm(request.user, request.POST)
            if form.is_valid():
                return self._handle_email_composition_form(request, 'forward', form, email)
        else:
            # Pre-populate form for forward
            initial_data = {
                'subject': f'Fwd: {email.subject}',
                'body_html': email.html_body or '',
                'body_plain': email.plain_body or '',
            }
            form = EmailComposeForm(request.user, initial=initial_data)
        
        # Show forward form
        return render(request, 'admin/sage_mailbox/compose_email.html', {
            'title': f'Forward: {email.subject}',
            'action': 'forward',
            'original_email': email,
            'form': form,
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
        })
    
    def get_queryset(self, request):
        """Add optimizations to queryset."""
        return super().get_queryset(request).select_related('mailbox', 'mailbox__server').annotate(
            attachment_count=Count('attachments')
        )
    
    def subject_truncated(self, obj):
        """Display truncated subject."""
        return Truncator(obj.subject).chars(60)
    subject_truncated.short_description = _('Subject')
    subject_truncated.admin_order_field = 'subject'
    
    def size_formatted(self, obj):
        """Display formatted file size."""
        return format_file_size(obj.size)
    size_formatted.short_description = _('Size')
    size_formatted.admin_order_field = 'size'
    
    def flag_indicators(self, obj):
        """Display flag indicators."""
        flags = []
        if obj.is_seen:
            flags.append('<span class="flag-seen" title="Seen">👁</span>')
        if obj.is_flagged:
            flags.append('<span class="flag-flagged" title="Flagged">🚩</span>')
        if obj.is_answered:
            flags.append('<span class="flag-answered" title="Answered">↩</span>')
        if obj.is_deleted:
            flags.append('<span class="flag-deleted" title="Deleted">🗑</span>')
        if obj.is_draft:
            flags.append('<span class="flag-draft" title="Draft">📝</span>')
        if obj.is_in_trash:
            flags.append('<span class="flag-trash" title="In Trash">🗑</span>')
        
        return format_html(' '.join(flags))
    flag_indicators.short_description = _('Flags')
    
    def attachment_count(self, obj):
        """Display attachment count."""
        count = obj.attachment_count
        if count > 0:
            return format_html('<span title="Attachments">📎 {}</span>', count)
        return '-'
    attachment_count.short_description = _('Attachments')
    attachment_count.admin_order_field = 'attachment_count'
    
    def headers_formatted(self, obj):
        """Display formatted headers."""
        if obj.headers:
            formatted_headers = json.dumps(obj.headers, indent=2)
            return format_html('<pre>{}</pre>', formatted_headers)
        return '-'
    headers_formatted.short_description = _('Headers')
    
    def raw_content_preview(self, obj):
        """Display raw content preview."""
        if obj.raw_content:
            preview = obj.raw_content[:1000].decode('utf-8', errors='ignore')
            return format_html('<pre>{}</pre>', preview)
        return '-'
    raw_content_preview.short_description = _('Raw Content Preview')
    
    # Remove the direct sage_imap implementation - use repository methods instead
    
    def mark_as_read_sage_imap(self, request, queryset):
        """Mark selected emails as read using repository method."""
        try:
            updated = Email.objects.mark_as_read(queryset)
            messages.success(request, f"✓ Marked {updated} email(s) as read")
        except Exception as e:
            messages.error(request, f"✗ Failed to mark emails as read: {e}")
    
    mark_as_read_sage_imap.short_description = _('Mark as read (repository)')
    
    def mark_as_unread_sage_imap(self, request, queryset):
        """Mark selected emails as unread using repository method."""
        try:
            updated = Email.objects.mark_as_unread(queryset)
            messages.success(request, f"✓ Marked {updated} email(s) as unread")
        except Exception as e:
            messages.error(request, f"✗ Failed to mark emails as unread: {e}")
    
    mark_as_unread_sage_imap.short_description = _('Mark as unread (repository)')
    
    def mark_as_flagged_sage_imap(self, request, queryset):
        """Mark selected emails as flagged using repository method."""
        try:
            updated = Email.objects.mark_as_flagged(queryset)
            messages.success(request, f"✓ Marked {updated} email(s) as flagged")
        except Exception as e:
            messages.error(request, f"✗ Failed to mark emails as flagged: {e}")
    
    mark_as_flagged_sage_imap.short_description = _('Mark as flagged (repository)')
    
    def mark_as_unflagged_sage_imap(self, request, queryset):
        """Mark selected emails as unflagged using repository method."""
        try:
            updated = Email.objects.mark_as_unflagged(queryset)
            messages.success(request, f"✓ Marked {updated} email(s) as unflagged")
        except Exception as e:
            messages.error(request, f"✗ Failed to mark emails as unflagged: {e}")
    
    mark_as_unflagged_sage_imap.short_description = _('Mark as unflagged (repository)')
    
    def move_to_trash_sage_imap(self, request, queryset):
        """Move selected emails to trash using repository method."""
        try:
            updated = Email.objects.move_to_trash(queryset)
            messages.success(request, f"✓ Moved {updated} email(s) to trash")
        except Exception as e:
            messages.error(request, f"✗ Failed to move emails to trash: {e}")
    
    move_to_trash_sage_imap.short_description = _('Move to trash (repository)')
    
    def restore_from_trash_sage_imap(self, request, queryset):
        """Restore selected emails from trash using repository method."""
        try:
            updated = Email.objects.restore_from_trash(queryset)
            messages.success(request, f"✓ Restored {updated} email(s) from trash")
        except Exception as e:
            messages.error(request, f"✗ Failed to restore emails from trash: {e}")
    
    restore_from_trash_sage_imap.short_description = _('Restore from trash (repository)')
    
    def permanent_delete_sage_imap(self, request, queryset):
        """Permanently delete selected emails using repository method."""
        try:
            deleted = Email.objects.permanent_delete(queryset)
            messages.success(request, f"✓ Permanently deleted {deleted} email(s)")
        except Exception as e:
            messages.error(request, f"✗ Failed to permanently delete emails: {e}")
    
    permanent_delete_sage_imap.short_description = _('Permanently delete (repository)')
    
    def download_as_eml_sage_imap(self, request, queryset):
        """Download selected emails as EML files using repository method."""
        if queryset.count() == 1:
            email = queryset.first()
            try:
                eml_content = Email.objects.download_as_eml(email)
                response = HttpResponse(eml_content, content_type='message/rfc822')
                response['Content-Disposition'] = f'attachment; filename="{email.subject or "email"}.eml"'
                return response
            except Exception as e:
                messages.error(request, f"✗ Failed to download email: {e}")
        else:
            messages.error(request, "Please select only one email for EML download")
    
    download_as_eml_sage_imap.short_description = _('Download as EML (repository)')
    
    def sync_flags_sage_imap(self, request, queryset):
        """Sync flags for selected emails using repository method."""
        try:
            # Use the existing sync method from the repository
            # This will refresh the emails from the server
            success_count = 0
            for email in queryset:
                try:
                    # Force refresh email from server by re-syncing
                    created, updated = Email.objects.sync_emails_from_server(
                        email.mailbox, full_sync=False, limit=1
                    )
                    success_count += 1
                except Exception as e:
                    logger.error(f"Flag sync failed for email {email.uid}: {e}")
                    continue
            
            messages.success(request, f"✓ Synced flags for {success_count} email(s)")
        except Exception as e:
            messages.error(request, f"✗ Failed to sync flags: {e}")
    
    sync_flags_sage_imap.short_description = _('Sync flags (repository)')
    
    def get_email_flags(self, request, queryset):
        """Get current flags for selected emails from database."""
        for email in queryset[:5]:  # Limit to first 5 emails
            flag_list = []
            if email.is_seen:
                flag_list.append('\\Seen')
            if email.is_flagged:
                flag_list.append('\\Flagged')
            if email.is_answered:
                flag_list.append('\\Answered')
            if email.is_deleted:
                flag_list.append('\\Deleted')
            if email.is_draft:
                flag_list.append('\\Draft')
            if email.is_recent:
                flag_list.append('\\Recent')
            
            messages.info(
                request,
                f"🏷 {email.subject[:50]}: {', '.join(flag_list) if flag_list else 'No flags'}"
            )
    
    get_email_flags.short_description = _('Get email flags (from database)')
    

    
    def _handle_email_composition_form(self, request, action, form, original_email=None):
        """Handle email composition form submission using Django form."""
        try:
            # Get cleaned form data
            smtp_server = form.cleaned_data['smtp_server']
            template = form.cleaned_data.get('template')
            to_addresses = form.cleaned_data['to_addresses']
            cc_addresses = form.cleaned_data['cc_addresses']
            bcc_addresses = form.cleaned_data['bcc_addresses']
            subject = form.cleaned_data['subject']
            body_html = form.cleaned_data['body_html']
            body_plain = form.cleaned_data['body_plain']
            priority = form.cleaned_data['priority']
            
            # Create email service
            from .services.email_service import EmailSendingService
            service = EmailSendingService(smtp_server=smtp_server)
            
            # Handle different actions
            if action == 'compose':
                # Send new email with IMAP Sent folder save
                email = service.send_email(
                    to_addresses=to_addresses,
                    subject=subject,
                    body_html=body_html,
                    body_plain=body_plain,
                    cc_addresses=cc_addresses,
                    bcc_addresses=bcc_addresses,
                    priority=priority,
                    template=template,
                    save_to_sent=True  # Save to IMAP Sent folder
                )
                
                messages.success(request, f"✓ Email '{subject}' sent successfully to {len(to_addresses)} recipient(s) and saved to Sent folder")
                
            elif action == 'reply':
                # Create reply with IMAP Sent folder save
                reply_email = service.create_reply(
                    original_email=original_email,
                    reply_body_html=body_html,
                    reply_body_plain=body_plain
                )
                
                # Update recipients if changed
                if to_addresses:
                    reply_email.to_addresses = to_addresses
                if cc_addresses:
                    reply_email.cc_addresses = cc_addresses
                if bcc_addresses:
                    reply_email.bcc_addresses = bcc_addresses
                
                reply_email.priority = priority
                reply_email.save()
                
                # Send reply with IMAP Sent folder save
                service.send_email(
                    to_addresses=reply_email.to_addresses,
                    subject=reply_email.subject,
                    body_html=reply_email.html_body,
                    body_plain=reply_email.plain_body,
                    cc_addresses=reply_email.cc_addresses,
                    bcc_addresses=reply_email.bcc_addresses,
                    priority=reply_email.priority,
                    in_reply_to=reply_email.in_reply_to,
                    references=reply_email.references,
                    template=template,
                    save_to_sent=True  # Save to IMAP Sent folder
                )
                
                messages.success(request, f"✓ Reply sent successfully and saved to Sent folder")
                
            elif action == 'forward':
                # Create forward with IMAP Sent folder save
                forward_email = service.create_forward(
                    original_email=original_email,
                    forward_body_html=body_html,
                    forward_body_plain=body_plain
                )
                
                # Update recipients
                forward_email.to_addresses = to_addresses
                forward_email.cc_addresses = cc_addresses
                forward_email.bcc_addresses = bcc_addresses
                forward_email.priority = priority
                forward_email.save()
                
                # Send forward with IMAP Sent folder save
                service.send_email(
                    to_addresses=forward_email.to_addresses,
                    subject=forward_email.subject,
                    body_html=forward_email.html_body,
                    body_plain=forward_email.plain_body,
                    cc_addresses=forward_email.cc_addresses,
                    bcc_addresses=forward_email.bcc_addresses,
                    priority=forward_email.priority,
                    template=template,
                    save_to_sent=True  # Save to IMAP Sent folder
                )
                
                messages.success(request, f"✓ Email forwarded successfully and saved to Sent folder")
            
            return redirect('admin:sage_mailbox_email_changelist')
            
        except Exception as e:
            messages.error(request, f"Failed to send email: {str(e)}")
            return redirect('admin:sage_mailbox_email_changelist')
    
    def _handle_email_composition(self, request, action, original_email=None):
        """Legacy method - redirects to form-based approach."""
        # This method kept for backwards compatibility
        if request.method == 'POST':
            form = EmailComposeForm(request.user, request.POST)
            if form.is_valid():
                return self._handle_email_composition_form(request, action, form, original_email)
            else:
                messages.error(request, "Please correct the errors in the form")
                return redirect('admin:sage_mailbox_email_changelist')
        return redirect('admin:sage_mailbox_email_changelist')


@admin.register(Attachment)
class AttachmentAdmin(BaseModelAdmin):
    """Admin interface for Attachment model."""
    
    list_display = [
        'filename', 'email_subject', 'content_type', 'size_formatted',
        'is_image_icon', 'created_at'
    ]
    list_display_links = ['filename']
    list_filter = ['content_type', 'created_at', 'email__mailbox']
    search_fields = ['filename', 'email__subject', 'content_type']
    readonly_fields = ['created_at', 'updated_at', 'size', 'checksum']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('email', 'filename', 'content_type', 'size')
        }),
        (_('Content'), {
            'fields': ('content_id', 'content_transfer_encoding', 'checksum')
        }),
        (_('File'), {
            'fields': ('file_path',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Add optimizations to queryset."""
        return super().get_queryset(request).select_related('email', 'email__mailbox')
    
    def email_subject(self, obj):
        """Display email subject."""
        return Truncator(obj.email.subject).chars(40)
    email_subject.short_description = _('Email Subject')
    
    def size_formatted(self, obj):
        """Display formatted file size."""
        return format_file_size(obj.size)
    size_formatted.short_description = _('Size')
    size_formatted.admin_order_field = 'size'
    
    def is_image_icon(self, obj):
        """Display image icon if attachment is image."""
        if obj.is_image:
            return format_html('<span title="Image">🖼</span>')
        return '-'
    is_image_icon.short_description = _('Image')


@admin.register(EmailFlag)
class EmailFlagAdmin(BaseModelAdmin):
    """Admin interface for Email Flag model."""
    
    list_display = ['email_subject', 'flag_name', 'flag_value', 'created_at']
    list_display_links = ['flag_name']
    list_filter = ['flag_name', 'created_at']
    search_fields = ['flag_name', 'flag_value', 'email__subject']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        """Add optimizations to queryset."""
        return super().get_queryset(request).select_related('email')
    
    def email_subject(self, obj):
        """Display email subject."""
        return Truncator(obj.email.subject).chars(40)
    email_subject.short_description = _('Email Subject')


# Custom admin site configuration
class MailboxAdminSite(admin.AdminSite):
    """Custom admin site for sage_mailbox with sage_imap integration."""
    
    site_header = _('Sage Mailbox Administration (sage_imap)')
    site_title = _('Sage Mailbox Admin')
    index_title = _('Email Management Dashboard with sage_imap')
    
    def get_app_list(self, request):
        """Customize app list for better organization."""
        app_list = super().get_app_list(request)
        
        # Reorganize models
        for app in app_list:
            if app['app_label'] == 'sage_mailbox':
                # Reorder models
                model_order = ['IMAPServer', 'Mailbox', 'Email', 'Attachment', 'EmailFlag']
                app['models'] = sorted(
                    app['models'],
                    key=lambda x: model_order.index(x['object_name']) if x['object_name'] in model_order else 999
                )
        
        return app_list


# Register custom admin site
mailbox_admin_site = MailboxAdminSite(name='mailbox_admin')
mailbox_admin_site.register(IMAPServer, IMAPServerAdmin)
mailbox_admin_site.register(Mailbox, MailboxAdmin)
mailbox_admin_site.register(Email, EmailAdmin)
mailbox_admin_site.register(Attachment, AttachmentAdmin)
mailbox_admin_site.register(EmailFlag, EmailFlagAdmin)

# Add CSS for better styling
admin.site.add_css = '''
<style>
.flag-seen { color: #28a745; }
.flag-flagged { color: #dc3545; }
.flag-answered { color: #17a2b8; }
.flag-deleted { color: #6c757d; }
.flag-draft { color: #ffc107; }
.flag-trash { color: #dc3545; }
.attachment-icon { color: #6c757d; }
.mailbox-icon { margin-right: 5px; }
.success-msg { color: #28a745; }
.error-msg { color: #dc3545; }
.info-msg { color: #17a2b8; }
</style>
'''
