"""
Attachment-related admin actions for sage_mailbox.

This module contains admin actions specifically for attachment management,
including cleanup operations and integrity verification.
"""

from django.contrib import messages
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from ...models import Attachment


def cleanup_orphaned_attachments_action(modeladmin, request, queryset):
    """
    Action to cleanup orphaned attachments.
    
    This action removes attachment records that no longer have
    associated email records, helping to clean up the database.
    """
    
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


def verify_attachment_integrity_action(modeladmin, request, queryset):
    """
    Action to verify attachment file integrity.
    
    This action checks if attachment files exist on disk and verifies
    their checksums to ensure data integrity.
    """
    
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


def download_attachments_action(modeladmin, request, queryset):
    """
    Action to download attachments as ZIP.
    
    This action creates a ZIP file containing all selected attachments
    for bulk download.
    """
    
    if queryset.count() == 0:
        messages.error(request, _('No attachments selected'))
        return
    
    from django.http import HttpResponse
    from ...utils import FileUtils
    
    files = []
    
    for attachment in queryset:
        try:
            if attachment.file_path and attachment.file_path.storage.exists(attachment.file_path.name):
                with attachment.file_path.open('rb') as f:
                    content = f.read()
                    filename = FileUtils.sanitize_filename(attachment.filename)
                    files.append((filename, content))
        except Exception as e:
            messages.warning(request, f"Failed to include {attachment.filename}: {e}")
    
    if not files:
        messages.error(request, _('No attachment files could be downloaded'))
        return
    
    # Create ZIP file
    zip_filename = f"attachments_{len(files)}_items.zip"
    zip_content = FileUtils.create_zip_file(files, zip_filename)
    
    response = HttpResponse(zip_content, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
    
    return response


def regenerate_checksums_action(modeladmin, request, queryset):
    """
    Action to regenerate checksums for attachments.
    
    This action recalculates and updates checksums for selected
    attachments to ensure data integrity tracking.
    """
    
    updated_count = 0
    error_count = 0
    
    for attachment in queryset:
        try:
            if attachment.file_path and attachment.file_path.storage.exists(attachment.file_path.name):
                import hashlib
                with attachment.file_path.open('rb') as f:
                    content = f.read()
                    new_checksum = hashlib.sha256(content).hexdigest()
                    
                    if attachment.checksum != new_checksum:
                        attachment.checksum = new_checksum
                        attachment.save(update_fields=['checksum'])
                        updated_count += 1
        except Exception as e:
            error_count += 1
            messages.warning(
                request,
                f"Error updating checksum for {attachment.filename}: {e}"
            )
    
    if updated_count > 0:
        messages.success(
            request,
            f"Updated checksums for {updated_count} attachment(s)"
        )
    
    if error_count > 0:
        messages.warning(
            request,
            f"Failed to update checksums for {error_count} attachment(s)"
        )
    
    if updated_count == 0 and error_count == 0:
        messages.info(request, _('All checksums are already up to date'))


# Action descriptions for admin
cleanup_orphaned_attachments_action.short_description = _('Cleanup orphaned attachments')
verify_attachment_integrity_action.short_description = _('Verify file integrity')
download_attachments_action.short_description = _('Download as ZIP')
regenerate_checksums_action.short_description = _('Regenerate checksums') 