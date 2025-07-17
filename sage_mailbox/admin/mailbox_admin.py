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
from ..models.proxy_models import (
    InboxMailbox, SentMailbox, DraftMailbox, TrashMailbox,
    SpamMailbox, CustomFolderMailbox
)
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


@admin.register(Mailbox)
class MailboxAdmin(BaseMailboxAdmin):
    """Admin interface for Mailbox model with sage_imap integration."""
    pass


# Specialized mailbox admin classes using proxy models
@admin.register(InboxMailbox)
class InboxMailboxAdmin(BaseMailboxAdmin):
    """Admin interface for inbox mailboxes."""
    
    def get_queryset(self, request):
        """Filter to show only inbox mailboxes."""
        qs = super().get_queryset(request)
        return qs.filter(name__icontains='inbox')


@admin.register(SentMailbox)
class SentMailboxAdmin(BaseMailboxAdmin):
    """Admin interface for sent mailboxes."""
    
    def get_queryset(self, request):
        """Filter to show only sent mailboxes."""
        qs = super().get_queryset(request)
        return qs.filter(name__icontains='sent')


@admin.register(DraftMailbox)
class DraftMailboxAdmin(BaseMailboxAdmin):
    """Admin interface for draft mailboxes."""
    
    def get_queryset(self, request):
        """Filter to show only draft mailboxes."""
        qs = super().get_queryset(request)
        return qs.filter(name__icontains='draft')


@admin.register(TrashMailbox)
class TrashMailboxAdmin(BaseMailboxAdmin):
    """Admin interface for trash mailboxes."""
    
    def get_queryset(self, request):
        """Filter to show only trash mailboxes."""
        qs = super().get_queryset(request)
        return qs.filter(name__icontains='trash')


@admin.register(SpamMailbox)
class SpamMailboxAdmin(BaseMailboxAdmin):
    """Admin interface for spam mailboxes."""
    
    def get_queryset(self, request):
        """Filter to show only spam mailboxes."""
        qs = super().get_queryset(request)
        return qs.filter(name__iregex=r'(spam|junk)')


@admin.register(CustomFolderMailbox)
class CustomFolderMailboxAdmin(BaseMailboxAdmin):
    """Admin interface for custom folder mailboxes."""
    
    def get_queryset(self, request):
        """Filter to show only custom folder mailboxes."""
        qs = super().get_queryset(request)
        return qs.filter(
            is_default=False
        ).exclude(
            name__iregex=r'(inbox|sent|draft|trash|spam|junk)'
        ) 