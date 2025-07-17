"""
Email-related signal handlers for sage_mailbox.

This module provides signal handlers for email operations including
creation, updates, deletions, and flag changes.
"""

import logging
from typing import Any, Dict, Optional

from django.db.models.signals import post_save, post_delete, pre_save, pre_delete
from django.dispatch import receiver, Signal
from django.utils import timezone

from ..models import Email, Mailbox, IMAPServer
from ..services.sync_service import EmailSyncService

logger = logging.getLogger(__name__)

# Custom signals for email operations
email_flag_changed = Signal()
email_moved = Signal()
email_restored = Signal()
email_permanently_deleted = Signal()
bulk_email_operation = Signal()


@receiver(post_save, sender=Email)
def handle_email_created(sender, instance: Email, created: bool, **kwargs):
    """
    Handle email creation.
    
    This signal is triggered when a new email is created.
    """
    if created:
        logger.info(f"Email created: {instance.subject} (UID: {instance.uid})")
        
        # Update mailbox statistics
        try:
            mailbox = instance.mailbox
            mailbox.message_count = mailbox.emails.count()
            mailbox.unseen_count = mailbox.emails.filter(is_seen=False).count()
            mailbox.save(update_fields=['message_count', 'unseen_count'])
        except Exception as e:
            logger.error(f"Failed to update mailbox stats after email creation: {e}")
        
        # Send notification for new email (if configured)
        if not instance.is_seen:
            send_new_email_notification(instance)


@receiver(post_save, sender=Email)
def handle_email_updated(sender, instance: Email, created: bool, **kwargs):
    """
    Handle email updates.
    
    This signal is triggered when an email is updated.
    """
    if not created:
        logger.debug(f"Email updated: {instance.subject} (UID: {instance.uid})")
        
        # Check if flags have changed
        if hasattr(instance, '_original_flags'):
            current_flags = set(instance.get_flags())
            original_flags = set(instance._original_flags)
            
            if current_flags != original_flags:
                email_flag_changed.send(
                    sender=sender,
                    instance=instance,
                    original_flags=original_flags,
                    current_flags=current_flags
                )
        
        # Update mailbox statistics if seen status changed
        try:
            mailbox = instance.mailbox
            mailbox.unseen_count = mailbox.emails.filter(is_seen=False).count()
            mailbox.save(update_fields=['unseen_count'])
        except Exception as e:
            logger.error(f"Failed to update mailbox unseen count: {e}")


@receiver(pre_save, sender=Email)
def handle_email_pre_save(sender, instance: Email, **kwargs):
    """
    Handle email pre-save to track changes.
    
    This signal is triggered before an email is saved.
    """
    if instance.pk:
        try:
            # Store original flags for comparison
            original = Email.objects.get(pk=instance.pk)
            instance._original_flags = original.get_flags()
            instance._original_mailbox = original.mailbox
        except Email.DoesNotExist:
            pass


@receiver(post_delete, sender=Email)
def handle_email_deleted(sender, instance: Email, **kwargs):
    """
    Handle email deletion.
    
    This signal is triggered when an email is deleted.
    """
    logger.info(f"Email deleted: {instance.subject} (UID: {instance.uid})")
    
    # Update mailbox statistics
    try:
        mailbox = instance.mailbox
        mailbox.message_count = mailbox.emails.count()
        mailbox.unseen_count = mailbox.emails.filter(is_seen=False).count()
        mailbox.save(update_fields=['message_count', 'unseen_count'])
    except Exception as e:
        logger.error(f"Failed to update mailbox stats after email deletion: {e}")
    
    # Clean up related attachments
    try:
        for attachment in instance.attachments.all():
            # Delete attachment file
            if attachment.file_path:
                try:
                    attachment.file_path.delete(save=False)
                except Exception as e:
                    logger.error(f"Failed to delete attachment file: {e}")
    except Exception as e:
        logger.error(f"Failed to clean up email attachments: {e}")


@receiver(email_flag_changed)
def handle_email_flag_changed(sender, instance: Email, original_flags: set, current_flags: set, **kwargs):
    """
    Handle email flag changes.
    
    This signal is triggered when email flags are changed.
    """
    added_flags = current_flags - original_flags
    removed_flags = original_flags - current_flags
    
    logger.info(
        f"Email flags changed for {instance.subject} (UID: {instance.uid}): "
        f"added={added_flags}, removed={removed_flags}"
    )
    
    # Handle specific flag changes
    if 'Seen' in added_flags:
        handle_email_marked_read(instance)
    elif 'Seen' in removed_flags:
        handle_email_marked_unread(instance)
    
    if 'Flagged' in added_flags:
        handle_email_flagged(instance)
    elif 'Flagged' in removed_flags:
        handle_email_unflagged(instance)


@receiver(email_moved)
def handle_email_moved(sender, instance: Email, from_mailbox: Mailbox, to_mailbox: Mailbox, **kwargs):
    """
    Handle email being moved between mailboxes.
    
    This signal is triggered when an email is moved to a different mailbox.
    """
    logger.info(
        f"Email moved: {instance.subject} (UID: {instance.uid}) "
        f"from {from_mailbox.name} to {to_mailbox.name}"
    )
    
    # Update statistics for both mailboxes
    try:
        # Update source mailbox
        from_mailbox.message_count = from_mailbox.emails.count()
        from_mailbox.unseen_count = from_mailbox.emails.filter(is_seen=False).count()
        from_mailbox.save(update_fields=['message_count', 'unseen_count'])
        
        # Update destination mailbox
        to_mailbox.message_count = to_mailbox.emails.count()
        to_mailbox.unseen_count = to_mailbox.emails.filter(is_seen=False).count()
        to_mailbox.save(update_fields=['message_count', 'unseen_count'])
    except Exception as e:
        logger.error(f"Failed to update mailbox stats after email move: {e}")


@receiver(email_restored)
def handle_email_restored(sender, instance: Email, **kwargs):
    """
    Handle email being restored from trash.
    
    This signal is triggered when an email is restored from trash.
    """
    logger.info(f"Email restored from trash: {instance.subject} (UID: {instance.uid})")
    
    # Update mailbox statistics
    try:
        mailbox = instance.mailbox
        mailbox.message_count = mailbox.emails.count()
        mailbox.unseen_count = mailbox.emails.filter(is_seen=False).count()
        mailbox.save(update_fields=['message_count', 'unseen_count'])
    except Exception as e:
        logger.error(f"Failed to update mailbox stats after email restoration: {e}")


@receiver(email_permanently_deleted)
def handle_email_permanently_deleted(sender, instance: Email, **kwargs):
    """
    Handle email being permanently deleted.
    
    This signal is triggered when an email is permanently deleted.
    """
    logger.info(f"Email permanently deleted: {instance.subject} (UID: {instance.uid})")
    
    # Audit log for permanent deletion
    create_audit_log('email_permanently_deleted', instance)


@receiver(bulk_email_operation)
def handle_bulk_email_operation(sender, operation: str, email_ids: list, **kwargs):
    """
    Handle bulk email operations.
    
    This signal is triggered when bulk operations are performed on emails.
    """
    logger.info(f"Bulk email operation: {operation} on {len(email_ids)} emails")
    
    # Update mailbox statistics after bulk operations
    try:
        # Get affected mailboxes
        affected_mailboxes = Mailbox.objects.filter(
            emails__id__in=email_ids
        ).distinct()
        
        # Update statistics for each mailbox
        for mailbox in affected_mailboxes:
            mailbox.message_count = mailbox.emails.count()
            mailbox.unseen_count = mailbox.emails.filter(is_seen=False).count()
            mailbox.save(update_fields=['message_count', 'unseen_count'])
    except Exception as e:
        logger.error(f"Failed to update mailbox stats after bulk operation: {e}")


def handle_email_marked_read(email: Email):
    """Handle email being marked as read."""
    logger.debug(f"Email marked as read: {email.subject}")
    
    # Update last read time or other read-related actions
    # This could trigger read receipt sending, analytics, etc.


def handle_email_marked_unread(email: Email):
    """Handle email being marked as unread."""
    logger.debug(f"Email marked as unread: {email.subject}")
    
    # Handle unread-related actions
    # This could trigger notifications, prioritization, etc.


def handle_email_flagged(email: Email):
    """Handle email being flagged."""
    logger.debug(f"Email flagged: {email.subject}")
    
    # Handle flagged-related actions
    # This could trigger priority notifications, categorization, etc.


def handle_email_unflagged(email: Email):
    """Handle email being unflagged."""
    logger.debug(f"Email unflagged: {email.subject}")
    
    # Handle unflagged-related actions


def send_new_email_notification(email: Email):
    """Send notification for new email."""
    try:
        # This is a placeholder for email notification logic
        # You could integrate with Django's messaging framework,
        # send push notifications, email alerts, etc.
        
        logger.info(f"New email notification: {email.subject} from {email.from_address}")
        
        # Example: Send email notification to user
        # from django.core.mail import send_mail
        # send_mail(
        #     subject=f"New Email: {email.subject}",
        #     message=f"You have a new email from {email.from_address}",
        #     from_email=settings.DEFAULT_FROM_EMAIL,
        #     recipient_list=[email.mailbox.server.owner.email],
        #     fail_silently=True,
        # )
        
    except Exception as e:
        logger.error(f"Failed to send new email notification: {e}")


def create_audit_log(action: str, email: Email, details: Optional[Dict[str, Any]] = None):
    """Create audit log entry for email operations."""
    try:
        # This is a placeholder for audit logging
        # You could integrate with Django's admin log, external logging services, etc.
        
        audit_data = {
            'action': action,
            'email_id': email.id,
            'email_subject': email.subject,
            'email_uid': email.uid,
            'mailbox': email.mailbox.name,
            'server': email.mailbox.server.name,
            'timestamp': timezone.now().isoformat(),
            'details': details or {},
        }
        
        logger.info(f"Audit log: {audit_data}")
        
        # Example: Save to audit log model
        # AuditLog.objects.create(**audit_data)
        
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")


def cleanup_email_data(email: Email):
    """Clean up email-related data after deletion."""
    try:
        # Clean up search indexes
        # if hasattr(email, 'search_index'):
        #     email.search_index.delete()
        
        # Clean up cached data
        # cache_key = f"email_{email.id}"
        # cache.delete(cache_key)
        
        # Clean up temporary files
        # temp_files = get_temp_files_for_email(email)
        # for temp_file in temp_files:
        #     os.remove(temp_file)
        
        logger.debug(f"Cleaned up data for email: {email.subject}")
        
    except Exception as e:
        logger.error(f"Failed to clean up email data: {e}")


# Helper functions for triggering custom signals
def trigger_email_moved(email: Email, from_mailbox: Mailbox, to_mailbox: Mailbox):
    """Trigger email moved signal."""
    email_moved.send(
        sender=Email,
        instance=email,
        from_mailbox=from_mailbox,
        to_mailbox=to_mailbox
    )


def trigger_email_restored(email: Email):
    """Trigger email restored signal."""
    email_restored.send(sender=Email, instance=email)


def trigger_email_permanently_deleted(email: Email):
    """Trigger email permanently deleted signal."""
    email_permanently_deleted.send(sender=Email, instance=email)


def trigger_bulk_email_operation(operation: str, email_ids: list):
    """Trigger bulk email operation signal."""
    bulk_email_operation.send(
        sender=Email,
        operation=operation,
        email_ids=email_ids
    ) 