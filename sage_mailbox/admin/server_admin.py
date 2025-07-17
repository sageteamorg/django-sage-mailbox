"""
Django admin configuration for server models.

This module provides admin interfaces for IMAP and SMTP server management
with full sage_imap integration and professional styling.
"""

from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.db.models import Count

from sage_imap.services.client import ConnectionConfig
from sage_imap import IMAPClient
from sage_imap.exceptions import IMAPConnectionError, IMAPAuthenticationError

from ..models import IMAPServer, SMTPServer, Mailbox
from ..forms import IMAPServerForm, SMTPServerForm
from .base import BaseModelAdmin


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
                from ..services.email_service import EmailSendingService
                
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