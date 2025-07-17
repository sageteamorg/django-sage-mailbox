"""
Synchronization-related signal handlers for sage_mailbox.

This module provides signal handlers for sync operations including
sync start, completion, failures, and progress tracking.
"""

import logging
from typing import Any, Dict, Optional

from django.dispatch import Signal, receiver
from django.utils import timezone

from ..models import Mailbox, IMAPServer
from ..services.sync_service import SyncResult

logger = logging.getLogger(__name__)

# Custom signals for sync operations
sync_started = Signal()
sync_completed = Signal()
sync_failed = Signal()
sync_progress = Signal()
mailbox_sync_started = Signal()
mailbox_sync_completed = Signal()
server_sync_started = Signal()
server_sync_completed = Signal()


@receiver(sync_started)
def handle_sync_started(sender, mailbox: Optional[Mailbox] = None, server: Optional[IMAPServer] = None, 
                       sync_type: str = 'incremental', **kwargs):
    """
    Handle synchronization start.
    
    This signal is triggered when a sync operation begins.
    """
    if mailbox:
        logger.info(f"Sync started for mailbox: {mailbox.name} (type: {sync_type})")
        
        # Update mailbox sync status
        # You could add a sync_status field to track ongoing syncs
        # mailbox.sync_status = 'syncing'
        # mailbox.sync_started_at = timezone.now()
        # mailbox.save(update_fields=['sync_status', 'sync_started_at'])
        
    elif server:
        logger.info(f"Sync started for server: {server.name} (type: {sync_type})")
        
        # Update server sync status
        # server.sync_status = 'syncing'
        # server.sync_started_at = timezone.now()
        # server.save(update_fields=['sync_status', 'sync_started_at'])
    
    # Send notification about sync start
    send_sync_notification('started', mailbox, server, sync_type)


@receiver(sync_completed)
def handle_sync_completed(sender, result: SyncResult, mailbox: Optional[Mailbox] = None, 
                         server: Optional[IMAPServer] = None, sync_type: str = 'incremental', **kwargs):
    """
    Handle synchronization completion.
    
    This signal is triggered when a sync operation completes successfully.
    """
    if mailbox:
        logger.info(
            f"Sync completed for mailbox: {mailbox.name} "
            f"(created: {result.created_count}, updated: {result.updated_count}, "
            f"time: {result.sync_time:.2f}s)"
        )
        
        # Update mailbox sync status
        mailbox.last_sync = timezone.now()
        mailbox.save(update_fields=['last_sync'])
        
    elif server:
        logger.info(
            f"Sync completed for server: {server.name} "
            f"(created: {result.created_count}, updated: {result.updated_count}, "
            f"time: {result.sync_time:.2f}s)"
        )
    
    # Log sync statistics
    log_sync_statistics(result, mailbox, server)
    
    # Send notification about sync completion
    send_sync_notification('completed', mailbox, server, sync_type, result)
    
    # Clean up temporary data
    cleanup_sync_data(mailbox, server)


@receiver(sync_failed)
def handle_sync_failed(sender, error: str, mailbox: Optional[Mailbox] = None, 
                      server: Optional[IMAPServer] = None, sync_type: str = 'incremental', **kwargs):
    """
    Handle synchronization failure.
    
    This signal is triggered when a sync operation fails.
    """
    if mailbox:
        logger.error(f"Sync failed for mailbox: {mailbox.name} - {error}")
        
        # Update mailbox with error status
        # mailbox.sync_status = 'failed'
        # mailbox.last_sync_error = error
        # mailbox.last_sync_error_at = timezone.now()
        # mailbox.save(update_fields=['sync_status', 'last_sync_error', 'last_sync_error_at'])
        
    elif server:
        logger.error(f"Sync failed for server: {server.name} - {error}")
        
        # Update server with error status
        # server.sync_status = 'failed'
        # server.last_sync_error = error
        # server.last_sync_error_at = timezone.now()
        # server.save(update_fields=['sync_status', 'last_sync_error', 'last_sync_error_at'])
    
    # Send error notification
    send_sync_error_notification(error, mailbox, server, sync_type)
    
    # Log error for debugging
    log_sync_error(error, mailbox, server, sync_type)


@receiver(sync_progress)
def handle_sync_progress(sender, progress: Dict[str, Any], mailbox: Optional[Mailbox] = None, 
                        server: Optional[IMAPServer] = None, **kwargs):
    """
    Handle synchronization progress updates.
    
    This signal is triggered during sync to report progress.
    """
    if mailbox:
        logger.debug(f"Sync progress for {mailbox.name}: {progress}")
    elif server:
        logger.debug(f"Sync progress for {server.name}: {progress}")
    
    # Update progress in cache or database
    update_sync_progress(progress, mailbox, server)


@receiver(mailbox_sync_started)
def handle_mailbox_sync_started(sender, mailbox: Mailbox, sync_type: str, **kwargs):
    """Handle mailbox sync start."""
    logger.info(f"Mailbox sync started: {mailbox.name} ({sync_type})")
    
    # Trigger general sync started signal
    sync_started.send(
        sender=sender,
        mailbox=mailbox,
        sync_type=sync_type
    )


@receiver(mailbox_sync_completed)
def handle_mailbox_sync_completed(sender, mailbox: Mailbox, result: SyncResult, 
                                 sync_type: str, **kwargs):
    """Handle mailbox sync completion."""
    logger.info(f"Mailbox sync completed: {mailbox.name} ({sync_type})")
    
    # Update mailbox statistics
    try:
        # These stats should already be updated by the sync service,
        # but we can add additional processing here
        pass
    except Exception as e:
        logger.error(f"Failed to update mailbox stats after sync: {e}")
    
    # Trigger general sync completed signal
    sync_completed.send(
        sender=sender,
        mailbox=mailbox,
        result=result,
        sync_type=sync_type
    )


@receiver(server_sync_started)
def handle_server_sync_started(sender, server: IMAPServer, sync_type: str, **kwargs):
    """Handle server sync start."""
    logger.info(f"Server sync started: {server.name} ({sync_type})")
    
    # Trigger general sync started signal
    sync_started.send(
        sender=sender,
        server=server,
        sync_type=sync_type
    )


@receiver(server_sync_completed)
def handle_server_sync_completed(sender, server: IMAPServer, result: SyncResult, 
                                sync_type: str, **kwargs):
    """Handle server sync completion."""
    logger.info(f"Server sync completed: {server.name} ({sync_type})")
    
    # Trigger general sync completed signal
    sync_completed.send(
        sender=sender,
        server=server,
        result=result,
        sync_type=sync_type
    )


def send_sync_notification(status: str, mailbox: Optional[Mailbox] = None, 
                          server: Optional[IMAPServer] = None, sync_type: str = 'incremental',
                          result: Optional[SyncResult] = None):
    """Send notification about sync status."""
    try:
        # This is a placeholder for notification logic
        # You could integrate with Django's messaging framework,
        # websockets for real-time updates, etc.
        
        if mailbox:
            message = f"Sync {status} for mailbox {mailbox.name}"
            if result:
                message += f" (created: {result.created_count}, updated: {result.updated_count})"
        elif server:
            message = f"Sync {status} for server {server.name}"
            if result:
                message += f" (created: {result.created_count}, updated: {result.updated_count})"
        else:
            message = f"Sync {status}"
        
        logger.info(f"Sync notification: {message}")
        
        # Example: Send real-time notification via WebSocket
        # from channels.layers import get_channel_layer
        # channel_layer = get_channel_layer()
        # async_to_sync(channel_layer.group_send)(
        #     "sync_updates",
        #     {
        #         "type": "sync_notification",
        #         "message": message,
        #         "status": status,
        #         "mailbox_id": mailbox.id if mailbox else None,
        #         "server_id": server.id if server else None,
        #         "result": result.__dict__ if result else None,
        #     }
        # )
        
    except Exception as e:
        logger.error(f"Failed to send sync notification: {e}")


def send_sync_error_notification(error: str, mailbox: Optional[Mailbox] = None, 
                                server: Optional[IMAPServer] = None, sync_type: str = 'incremental'):
    """Send error notification for sync failures."""
    try:
        if mailbox:
            message = f"Sync failed for mailbox {mailbox.name}: {error}"
            # Send email to mailbox owner
            # send_mail(
            #     subject=f"Sync Error - {mailbox.name}",
            #     message=message,
            #     from_email=settings.DEFAULT_FROM_EMAIL,
            #     recipient_list=[mailbox.server.owner.email],
            #     fail_silently=True,
            # )
        elif server:
            message = f"Sync failed for server {server.name}: {error}"
            # Send email to server owner
            # send_mail(
            #     subject=f"Sync Error - {server.name}",
            #     message=message,
            #     from_email=settings.DEFAULT_FROM_EMAIL,
            #     recipient_list=[server.owner.email],
            #     fail_silently=True,
            # )
        
        logger.error(f"Sync error notification: {message}")
        
    except Exception as e:
        logger.error(f"Failed to send sync error notification: {e}")


def log_sync_statistics(result: SyncResult, mailbox: Optional[Mailbox] = None, 
                       server: Optional[IMAPServer] = None):
    """Log detailed sync statistics."""
    try:
        stats = {
            'created_count': result.created_count,
            'updated_count': result.updated_count,
            'deleted_count': result.deleted_count,
            'skipped_count': result.skipped_count,
            'error_count': result.error_count,
            'total_processed': result.total_processed,
            'sync_time': result.sync_time,
            'errors': result.errors,
            'timestamp': timezone.now().isoformat(),
        }
        
        if mailbox:
            stats['mailbox_id'] = mailbox.id
            stats['mailbox_name'] = mailbox.name
            stats['server_id'] = mailbox.server.id
            stats['server_name'] = mailbox.server.name
        elif server:
            stats['server_id'] = server.id
            stats['server_name'] = server.name
        
        logger.info(f"Sync statistics: {stats}")
        
        # Example: Save to metrics/analytics system
        # metrics.record_sync_stats(stats)
        
    except Exception as e:
        logger.error(f"Failed to log sync statistics: {e}")


def log_sync_error(error: str, mailbox: Optional[Mailbox] = None, 
                  server: Optional[IMAPServer] = None, sync_type: str = 'incremental'):
    """Log detailed sync error information."""
    try:
        error_data = {
            'error': error,
            'sync_type': sync_type,
            'timestamp': timezone.now().isoformat(),
        }
        
        if mailbox:
            error_data.update({
                'mailbox_id': mailbox.id,
                'mailbox_name': mailbox.name,
                'server_id': mailbox.server.id,
                'server_name': mailbox.server.name,
                'server_host': mailbox.server.host,
            })
        elif server:
            error_data.update({
                'server_id': server.id,
                'server_name': server.name,
                'server_host': server.host,
            })
        
        logger.error(f"Sync error details: {error_data}")
        
        # Example: Save to error tracking system
        # error_tracker.record_sync_error(error_data)
        
    except Exception as e:
        logger.error(f"Failed to log sync error details: {e}")


def update_sync_progress(progress: Dict[str, Any], mailbox: Optional[Mailbox] = None, 
                        server: Optional[IMAPServer] = None):
    """Update sync progress in cache or database."""
    try:
        # Example: Store progress in cache for real-time updates
        # from django.core.cache import cache
        
        if mailbox:
            cache_key = f"sync_progress_mailbox_{mailbox.id}"
        elif server:
            cache_key = f"sync_progress_server_{server.id}"
        else:
            return
        
        progress_data = {
            'progress': progress,
            'timestamp': timezone.now().isoformat(),
        }
        
        # cache.set(cache_key, progress_data, timeout=300)  # 5 minutes
        
        logger.debug(f"Updated sync progress: {cache_key} = {progress_data}")
        
    except Exception as e:
        logger.error(f"Failed to update sync progress: {e}")


def cleanup_sync_data(mailbox: Optional[Mailbox] = None, server: Optional[IMAPServer] = None):
    """Clean up temporary sync data."""
    try:
        # Clean up progress cache
        if mailbox:
            cache_key = f"sync_progress_mailbox_{mailbox.id}"
        elif server:
            cache_key = f"sync_progress_server_{server.id}"
        else:
            return
        
        # from django.core.cache import cache
        # cache.delete(cache_key)
        
        # Clean up temporary files
        # temp_dir = f"/tmp/sage_mailbox_sync_{mailbox.id if mailbox else server.id}"
        # if os.path.exists(temp_dir):
        #     shutil.rmtree(temp_dir)
        
        logger.debug(f"Cleaned up sync data for {cache_key}")
        
    except Exception as e:
        logger.error(f"Failed to clean up sync data: {e}")


# Helper functions for triggering sync signals
def trigger_sync_started(mailbox: Optional[Mailbox] = None, server: Optional[IMAPServer] = None, 
                        sync_type: str = 'incremental'):
    """Trigger sync started signal."""
    if mailbox:
        mailbox_sync_started.send(
            sender=Mailbox,
            mailbox=mailbox,
            sync_type=sync_type
        )
    elif server:
        server_sync_started.send(
            sender=IMAPServer,
            server=server,
            sync_type=sync_type
        )


def trigger_sync_completed(result: SyncResult, mailbox: Optional[Mailbox] = None, 
                          server: Optional[IMAPServer] = None, sync_type: str = 'incremental'):
    """Trigger sync completed signal."""
    if mailbox:
        mailbox_sync_completed.send(
            sender=Mailbox,
            mailbox=mailbox,
            result=result,
            sync_type=sync_type
        )
    elif server:
        server_sync_completed.send(
            sender=IMAPServer,
            server=server,
            result=result,
            sync_type=sync_type
        )


def trigger_sync_failed(error: str, mailbox: Optional[Mailbox] = None, 
                       server: Optional[IMAPServer] = None, sync_type: str = 'incremental'):
    """Trigger sync failed signal."""
    sync_failed.send(
        sender=Mailbox if mailbox else IMAPServer,
        error=error,
        mailbox=mailbox,
        server=server,
        sync_type=sync_type
    )


def trigger_sync_progress(progress: Dict[str, Any], mailbox: Optional[Mailbox] = None, 
                         server: Optional[IMAPServer] = None):
    """Trigger sync progress signal."""
    sync_progress.send(
        sender=Mailbox if mailbox else IMAPServer,
        progress=progress,
        mailbox=mailbox,
        server=server
    ) 