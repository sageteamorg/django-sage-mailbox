"""
Attachment-related signal handlers for sage_mailbox.

This module provides signal handlers for attachment operations including
file creation, deletion, integrity checks, and cleanup.
"""

import logging
import os
from typing import Optional

from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver, Signal
from django.utils import timezone

from ..models import Attachment, Email
from ..services.attachment_service import AttachmentService

logger = logging.getLogger(__name__)

# Custom signals for attachment operations
attachment_file_created = Signal()
attachment_file_deleted = Signal()
attachment_integrity_check = Signal()
attachment_orphaned = Signal()


@receiver(post_save, sender=Attachment)
def handle_attachment_created(sender, instance: Attachment, created: bool, **kwargs):
    """
    Handle attachment creation.
    
    This signal is triggered when a new attachment is created.
    """
    if created:
        logger.info(f"Attachment created: {instance.filename} ({instance.size} bytes)")
        
        # Update email attachment count
        try:
            email = instance.email
            attachment_count = email.attachments.count()
            # You could add an attachment_count field to Email model for optimization
            # email.attachment_count = attachment_count
            # email.save(update_fields=['attachment_count'])
        except Exception as e:
            logger.error(f"Failed to update email attachment count: {e}")
        
        # Trigger file created signal
        if instance.file_path:
            attachment_file_created.send(
                sender=sender,
                instance=instance,
                file_path=instance.file_path.name
            )
        
        # Log attachment creation for audit
        log_attachment_operation('created', instance)


@receiver(pre_delete, sender=Attachment)
def handle_attachment_pre_delete(sender, instance: Attachment, **kwargs):
    """
    Handle attachment pre-deletion to clean up files.
    
    This signal is triggered before an attachment is deleted.
    """
    logger.info(f"Preparing to delete attachment: {instance.filename}")
    
    # Store file path for cleanup after deletion
    if instance.file_path:
        instance._file_path_to_delete = instance.file_path.name
    
    # Log attachment deletion for audit
    log_attachment_operation('pre_delete', instance)


@receiver(post_delete, sender=Attachment)
def handle_attachment_deleted(sender, instance: Attachment, **kwargs):
    """
    Handle attachment deletion.
    
    This signal is triggered when an attachment is deleted.
    """
    logger.info(f"Attachment deleted: {instance.filename}")
    
    # Clean up file if it exists
    if hasattr(instance, '_file_path_to_delete'):
        try:
            attachment_service = AttachmentService()
            # Create a temporary attachment object for file deletion
            temp_attachment = type('TempAttachment', (), {
                'file_path': type('FilePath', (), {'name': instance._file_path_to_delete})()
            })()
            attachment_service.delete_attachment_file(temp_attachment)
            
            # Trigger file deleted signal
            attachment_file_deleted.send(
                sender=sender,
                instance=instance,
                file_path=instance._file_path_to_delete
            )
        except Exception as e:
            logger.error(f"Failed to delete attachment file: {e}")
    
    # Update email attachment count
    try:
        if hasattr(instance, 'email') and instance.email:
            email = instance.email
            attachment_count = email.attachments.count()
            # email.attachment_count = attachment_count
            # email.save(update_fields=['attachment_count'])
    except Exception as e:
        logger.error(f"Failed to update email attachment count after deletion: {e}")
    
    # Log attachment deletion for audit
    log_attachment_operation('deleted', instance)


@receiver(attachment_file_created)
def handle_attachment_file_created(sender, instance: Attachment, file_path: str, **kwargs):
    """
    Handle attachment file creation.
    
    This signal is triggered when an attachment file is created.
    """
    logger.debug(f"Attachment file created: {file_path}")
    
    # Verify file integrity
    try:
        attachment_service = AttachmentService()
        if attachment_service.verify_attachment_integrity(instance):
            logger.debug(f"Attachment file integrity verified: {file_path}")
        else:
            logger.warning(f"Attachment file integrity check failed: {file_path}")
            
            # Trigger integrity check signal
            attachment_integrity_check.send(
                sender=sender,
                instance=instance,
                status='failed',
                file_path=file_path
            )
    except Exception as e:
        logger.error(f"Failed to verify attachment integrity: {e}")
    
    # Update storage statistics
    update_storage_statistics()


@receiver(attachment_file_deleted)
def handle_attachment_file_deleted(sender, instance: Attachment, file_path: str, **kwargs):
    """
    Handle attachment file deletion.
    
    This signal is triggered when an attachment file is deleted.
    """
    logger.debug(f"Attachment file deleted: {file_path}")
    
    # Update storage statistics
    update_storage_statistics()
    
    # Clean up any cached data related to this file
    cleanup_attachment_cache(instance)


@receiver(attachment_integrity_check)
def handle_attachment_integrity_check(sender, instance: Attachment, status: str, 
                                     file_path: str, **kwargs):
    """
    Handle attachment integrity check results.
    
    This signal is triggered when an attachment integrity check is performed.
    """
    if status == 'failed':
        logger.error(f"Attachment integrity check failed: {file_path}")
        
        # Mark attachment as corrupted
        # You could add a status field to track attachment health
        # instance.status = 'corrupted'
        # instance.save(update_fields=['status'])
        
        # Send notification about corrupted file
        send_corruption_notification(instance)
        
        # Attempt to re-download from email if possible
        attempt_attachment_recovery(instance)
    else:
        logger.debug(f"Attachment integrity check passed: {file_path}")


@receiver(attachment_orphaned)
def handle_attachment_orphaned(sender, instance: Attachment, **kwargs):
    """
    Handle orphaned attachment detection.
    
    This signal is triggered when an attachment is detected as orphaned.
    """
    logger.warning(f"Orphaned attachment detected: {instance.filename}")
    
    # Clean up orphaned attachment
    try:
        attachment_service = AttachmentService()
        attachment_service.delete_attachment_file(instance)
        instance.delete()
        logger.info(f"Cleaned up orphaned attachment: {instance.filename}")
    except Exception as e:
        logger.error(f"Failed to clean up orphaned attachment: {e}")


def log_attachment_operation(operation: str, attachment: Attachment):
    """Log attachment operations for audit purposes."""
    try:
        audit_data = {
            'operation': operation,
            'attachment_id': attachment.id,
            'filename': attachment.filename,
            'size': attachment.size,
            'content_type': attachment.content_type,
            'email_id': attachment.email.id if attachment.email else None,
            'email_subject': attachment.email.subject if attachment.email else None,
            'timestamp': timezone.now().isoformat(),
        }
        
        logger.info(f"Attachment audit: {audit_data}")
        
        # Example: Save to audit log
        # AuditLog.objects.create(
        #     action=operation,
        #     object_type='attachment',
        #     object_id=attachment.id,
        #     data=audit_data,
        # )
        
    except Exception as e:
        logger.error(f"Failed to log attachment operation: {e}")


def update_storage_statistics():
    """Update storage statistics after file operations."""
    try:
        # This could update cached storage statistics
        # from django.core.cache import cache
        # attachment_service = AttachmentService()
        # stats = attachment_service.get_storage_statistics()
        # cache.set('storage_statistics', stats, timeout=3600)  # 1 hour
        
        logger.debug("Updated storage statistics")
        
    except Exception as e:
        logger.error(f"Failed to update storage statistics: {e}")


def cleanup_attachment_cache(attachment: Attachment):
    """Clean up cached data for an attachment."""
    try:
        # Clean up any cached thumbnails, previews, etc.
        # cache_keys = [
        #     f"attachment_thumbnail_{attachment.id}",
        #     f"attachment_preview_{attachment.id}",
        #     f"attachment_metadata_{attachment.id}",
        # ]
        # 
        # from django.core.cache import cache
        # cache.delete_many(cache_keys)
        
        logger.debug(f"Cleaned up cache for attachment: {attachment.filename}")
        
    except Exception as e:
        logger.error(f"Failed to clean up attachment cache: {e}")


def send_corruption_notification(attachment: Attachment):
    """Send notification about corrupted attachment."""
    try:
        # Send notification to administrators or email owner
        message = f"Attachment corruption detected: {attachment.filename}"
        
        if attachment.email and attachment.email.mailbox:
            owner = attachment.email.mailbox.server.owner
            logger.warning(f"Corrupted attachment notification for {owner.username}: {message}")
            
            # Example: Send email notification
            # from django.core.mail import send_mail
            # send_mail(
            #     subject="Attachment Corruption Detected",
            #     message=message,
            #     from_email=settings.DEFAULT_FROM_EMAIL,
            #     recipient_list=[owner.email],
            #     fail_silently=True,
            # )
        
    except Exception as e:
        logger.error(f"Failed to send corruption notification: {e}")


def attempt_attachment_recovery(attachment: Attachment):
    """Attempt to recover a corrupted attachment from the original email."""
    try:
        # This would attempt to re-download the attachment from the email source
        if attachment.email and attachment.email.raw_content:
            logger.info(f"Attempting to recover attachment: {attachment.filename}")
            
            # Parse original email and extract attachment
            from sage_imap.models.email import EmailMessage as SageEmailMessage
            sage_email = SageEmailMessage.from_eml(attachment.email.raw_content)
            
            # Find matching attachment
            for sage_attachment in sage_email.attachments:
                if sage_attachment.filename == attachment.filename:
                    # Re-save the attachment
                    attachment_service = AttachmentService()
                    new_path = attachment_service._save_attachment_file(
                        attachment, sage_attachment.payload
                    )
                    
                    # Update attachment record
                    attachment.file_path = new_path
                    attachment.checksum = hashlib.sha256(sage_attachment.payload).hexdigest()
                    attachment.save()
                    
                    logger.info(f"Successfully recovered attachment: {attachment.filename}")
                    return True
        
        logger.warning(f"Could not recover attachment: {attachment.filename}")
        return False
        
    except Exception as e:
        logger.error(f"Failed to recover attachment {attachment.filename}: {e}")
        return False


def check_attachment_orphans():
    """Check for orphaned attachments and trigger cleanup."""
    try:
        # Find attachments without corresponding emails
        orphaned_attachments = Attachment.objects.filter(email__isnull=True)
        
        for attachment in orphaned_attachments:
            attachment_orphaned.send(
                sender=Attachment,
                instance=attachment
            )
        
        # Find attachments with missing files
        for attachment in Attachment.objects.exclude(file_path=''):
            attachment_service = AttachmentService()
            if not attachment_service.storage.exists(attachment.file_path.name):
                logger.warning(f"Missing file for attachment: {attachment.filename}")
                # You could trigger a recovery attempt or mark as missing
        
    except Exception as e:
        logger.error(f"Failed to check attachment orphans: {e}")


def cleanup_old_attachments(days_old: int = 90):
    """Clean up old deleted email attachments."""
    try:
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        # Find attachments from deleted emails that are old
        old_attachments = Attachment.objects.filter(
            email__is_deleted=True,
            email__deleted_at__lt=cutoff_date
        )
        
        deleted_count = 0
        for attachment in old_attachments:
            try:
                attachment_service = AttachmentService()
                attachment_service.delete_attachment_file(attachment)
                attachment.delete()
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete old attachment {attachment.filename}: {e}")
        
        logger.info(f"Cleaned up {deleted_count} old attachments")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Failed to cleanup old attachments: {e}")
        return 0


def generate_attachment_thumbnails(attachment: Attachment):
    """Generate thumbnails for image attachments."""
    try:
        if attachment.is_image and attachment.file_path:
            # This would generate thumbnails for image files
            # from PIL import Image
            # import io
            
            # content = attachment_service.download_attachment(attachment)
            # if content:
            #     image = Image.open(io.BytesIO(content))
            #     
            #     # Generate different sizes
            #     sizes = [(150, 150), (300, 300), (800, 600)]
            #     for size in sizes:
            #         thumbnail = image.copy()
            #         thumbnail.thumbnail(size, Image.Resampling.LANCZOS)
            #         
            #         # Save thumbnail
            #         thumb_path = f"thumbnails/{attachment.id}_{size[0]}x{size[1]}.jpg"
            #         # Save to storage...
            
            logger.debug(f"Generated thumbnails for: {attachment.filename}")
            
    except Exception as e:
        logger.error(f"Failed to generate thumbnails for {attachment.filename}: {e}")


# Helper functions for triggering attachment signals
def trigger_attachment_file_created(attachment: Attachment, file_path: str):
    """Trigger attachment file created signal."""
    attachment_file_created.send(
        sender=Attachment,
        instance=attachment,
        file_path=file_path
    )


def trigger_attachment_file_deleted(attachment: Attachment, file_path: str):
    """Trigger attachment file deleted signal."""
    attachment_file_deleted.send(
        sender=Attachment,
        instance=attachment,
        file_path=file_path
    )


def trigger_attachment_integrity_check(attachment: Attachment, status: str, file_path: str):
    """Trigger attachment integrity check signal."""
    attachment_integrity_check.send(
        sender=Attachment,
        instance=attachment,
        status=status,
        file_path=file_path
    )


def trigger_attachment_orphaned(attachment: Attachment):
    """Trigger attachment orphaned signal."""
    attachment_orphaned.send(
        sender=Attachment,
        instance=attachment
    ) 