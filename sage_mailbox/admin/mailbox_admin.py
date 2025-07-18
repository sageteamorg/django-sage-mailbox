"""
Django admin configuration for mailbox models.

This module provides admin interfaces for managing mailboxes
with full sage_imap integration and synchronization capabilities.
"""

from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from sage_imap.services.client import ConnectionConfig
from sage_imap import IMAPClient, IMAPFolderService

from ..models import Mailbox, Email
# Proxy models removed as requested
from ..utils import MailboxUtils
from .base import BaseModelAdmin


class BaseMailboxAdmin(BaseModelAdmin):
    """Base admin class for all mailbox proxy models."""
    
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
                    
                    # Get folder info using select method instead of list
                    try:
                        # Try to select the mailbox to get info
                        result = client.select(mailbox.name, readonly=True)
                        if result:
                            status, message_count = result
                            info_text = f"📂 {mailbox.name}: "
                            info_text += f"Status: {status}, "
                            info_text += f"Messages: {message_count}"
                            
                            # Try to get additional folder info
                            try:
                                folder_info = folder_service.get_folder_info(mailbox.name)
                                info_text += f", Selectable: {folder_info.selectable}, "
                                info_text += f"Has Children: {folder_info.has_children}, "
                                info_text += f"Attributes: {', '.join(folder_info.attributes)}"
                            except:
                                # If detailed info fails, just show basic info
                                pass
                            
                            messages.info(request, info_text)
                        else:
                            messages.warning(request, f"⚠ {mailbox.name}: Unable to select mailbox")
                            
                    except Exception as select_error:
                        # If select fails, try to get basic folder list
                        try:
                            folders = folder_service.list_folders(pattern="*")
                            matching_folders = [f for f in folders if f.name == mailbox.name]
                            if matching_folders:
                                folder = matching_folders[0]
                                info_text = f"📂 {mailbox.name}: "
                                info_text += f"Selectable: {folder.selectable}, "
                                info_text += f"Has Children: {folder.has_children}, "
                                info_text += f"Attributes: {', '.join(folder.attributes)}"
                                messages.info(request, info_text)
                            else:
                                messages.warning(request, f"⚠ {mailbox.name}: Mailbox not found in folder list")
                        except Exception as list_error:
                            messages.error(request, f"✗ {mailbox.name}: Failed to get folder info - {list_error}")
                    
            except Exception as e:
                messages.error(request, f"✗ {mailbox.name}: Failed to connect - {e}")
    
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


@admin.register(Mailbox)
class MailboxAdmin(BaseMailboxAdmin):
    """Admin interface for Mailbox model with sage_imap integration."""
    autocomplete_fields = ['server', 'parent']


# Proxy admin classes removed as requested - use filters instead 