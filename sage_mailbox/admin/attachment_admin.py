"""
Django admin configuration for attachment and flag models.

This module provides admin interfaces for managing attachments and email flags
with file handling and integrity verification capabilities.
"""

from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _

from ..models import Attachment, EmailFlag
from ..utils import format_file_size
from .base import BaseModelAdmin


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
    autocomplete_fields = ['email']
    
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
    
    actions = [
        'cleanup_orphaned_attachments', 'verify_attachment_integrity', 
        'download_attachments', 'regenerate_checksums'
    ]
    
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
    
    def cleanup_orphaned_attachments(self, request, queryset):
        """Cleanup orphaned attachments."""
        from django.db import transaction
        
        orphaned_count = 0
        
        with transaction.atomic():
            for attachment in queryset:
                if not attachment.email_id:
                    attachment.delete()
                    orphaned_count += 1
        
        if orphaned_count > 0:
            messages.success(
                request,
                f"Cleaned up {orphaned_count} orphaned attachment(s)"
            )
        else:
            messages.info(request, _('No orphaned attachments found'))
    
    cleanup_orphaned_attachments.short_description = _('Cleanup orphaned attachments')
    
    def verify_attachment_integrity(self, request, queryset):
        """Verify attachment file integrity."""
        missing_files = 0
        corrupted_files = 0
        
        for attachment in queryset:
            try:
                if attachment.file_path:
                    # Check if file exists
                    if not attachment.file_path.storage.exists(attachment.file_path.name):
                        missing_files += 1
                        continue
                    
                    # Verify checksum if available
                    if attachment.checksum:
                        import hashlib
                        with attachment.file_path.open('rb') as f:
                            content = f.read()
                            calculated_checksum = hashlib.sha256(content).hexdigest()
                            
                            if calculated_checksum != attachment.checksum:
                                corrupted_files += 1
            except Exception as e:
                messages.warning(
                    request,
                    f"Error checking attachment {attachment.filename}: {e}"
                )
        
        if missing_files > 0 or corrupted_files > 0:
            messages.warning(
                request,
                f"Found {missing_files} missing and {corrupted_files} corrupted file(s)"
            )
        else:
            messages.success(request, _('All attachment files are intact'))
    
    verify_attachment_integrity.short_description = _('Verify file integrity')
    
    def download_attachments(self, request, queryset):
        """Download selected attachments as ZIP."""
        if queryset.count() == 0:
            messages.error(request, _('No attachments selected'))
            return
        
        from django.http import HttpResponse
        from ..utils import FileUtils
        
        files = []
        for attachment in queryset:
            try:
                if attachment.file_path and attachment.file_path.storage.exists(attachment.file_path.name):
                    with attachment.file_path.open('rb') as f:
                        content = f.read()
                        files.append((attachment.filename, content))
            except Exception as e:
                messages.warning(request, f"Failed to include attachment {attachment.filename}: {e}")
        
        if not files:
            messages.error(request, _('No attachment files could be downloaded'))
            return
        
        # Create ZIP file
        zip_filename = f"attachments_{len(files)}_items.zip"
        zip_content = FileUtils.create_zip_file(files, zip_filename)
        
        response = HttpResponse(zip_content, content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
        
        return response
    
    download_attachments.short_description = _('Download attachments')
    
    def regenerate_checksums(self, request, queryset):
        """Regenerate checksums for selected attachments."""
        updated_count = 0
        
        for attachment in queryset:
            try:
                if attachment.file_path and attachment.file_path.storage.exists(attachment.file_path.name):
                    import hashlib
                    with attachment.file_path.open('rb') as f:
                        content = f.read()
                        new_checksum = hashlib.sha256(content).hexdigest()
                        attachment.checksum = new_checksum
                        attachment.save(update_fields=['checksum'])
                        updated_count += 1
            except Exception as e:
                messages.warning(request, f"Failed to regenerate checksum for {attachment.filename}: {e}")
        
        if updated_count > 0:
            messages.success(request, f"Regenerated checksums for {updated_count} attachment(s)")
        else:
            messages.info(request, _('No checksums were regenerated'))
    
    regenerate_checksums.short_description = _('Regenerate checksums')


@admin.register(EmailFlag)
class EmailFlagAdmin(BaseModelAdmin):
    """Admin interface for Email Flag model."""
    
    list_display = ['email_subject', 'flag_name', 'flag_value', 'created_at']
    list_display_links = ['flag_name']
    list_filter = ['flag_name', 'created_at']
    search_fields = ['flag_name', 'flag_value', 'email__subject']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('email', 'flag_name', 'flag_value')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['sync_flags_with_server', 'cleanup_invalid_flags']
    
    def get_queryset(self, request):
        """Add optimizations to queryset."""
        return super().get_queryset(request).select_related('email')
    
    def email_subject(self, obj):
        """Display email subject."""
        return Truncator(obj.email.subject).chars(40)
    email_subject.short_description = _('Email Subject')
    
    def sync_flags_with_server(self, request, queryset):
        """Sync flags with IMAP server."""
        synced_count = 0
        
        for flag in queryset:
            try:
                # Use repository method to sync the email's flags
                from ..models import Email
                created, updated = Email.objects.sync_emails_from_server(
                    flag.email.mailbox, full_sync=False, limit=1
                )
                synced_count += 1
            except Exception as e:
                messages.warning(request, f"Failed to sync flag for email {flag.email.subject}: {e}")
        
        if synced_count > 0:
            messages.success(request, f"Synced flags for {synced_count} email(s)")
        else:
            messages.info(request, _('No flags were synced'))
    
    sync_flags_with_server.short_description = _('Sync flags with server')
    
    def cleanup_invalid_flags(self, request, queryset):
        """Cleanup invalid or orphaned flags."""
        from django.db import transaction
        
        cleaned_count = 0
        
        with transaction.atomic():
            for flag in queryset:
                if not flag.email_id or not flag.flag_name:
                    flag.delete()
                    cleaned_count += 1
        
        if cleaned_count > 0:
            messages.success(request, f"Cleaned up {cleaned_count} invalid flag(s)")
        else:
            messages.info(request, _('No invalid flags found'))
    
    cleanup_invalid_flags.short_description = _('Cleanup invalid flags') 