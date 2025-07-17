"""
Email synchronization service for sage_mailbox.

This module provides comprehensive email synchronization capabilities
using the full power of sage_imap API.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from sage_imap.helpers.enums import Flag, MessagePart
from sage_imap.helpers.search import IMAPSearchCriteria
from sage_imap.models.email import EmailMessage as SageEmailMessage
from sage_imap.models.message import MessageSet
from sage_imap.services.client import IMAPClient, ConnectionConfig
from sage_imap.services.mailbox import IMAPMailboxService, IMAPMailboxUIDService
from sage_imap.services.flag import IMAPFlagService

logger = logging.getLogger(__name__)


@dataclass
class SyncOptions:
    """Configuration options for email synchronization."""
    full_sync: bool = False
    limit: Optional[int] = None
    batch_size: int = 50
    include_deleted: bool = False
    sync_flags: bool = True
    sync_attachments: bool = True


@dataclass
class SyncResult:
    """Result of synchronization operation."""
    success: bool
    mailbox_name: str
    total_emails: int
    new_emails: int
    updated_emails: int
    deleted_emails: int
    errors: List[str]
    execution_time: float
    
    @property
    def processed_emails(self) -> int:
        return self.new_emails + self.updated_emails + self.deleted_emails


class EmailSyncService:
    """Service for synchronizing emails between IMAP server and database."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def sync_mailbox(self, mailbox, sync_options: SyncOptions = None) -> SyncResult:
        """
        Synchronize emails for a specific mailbox using full sage_imap capabilities.
        
        Args:
            mailbox: Mailbox instance to sync
            sync_options: Configuration options for sync
            
        Returns:
            SyncResult with detailed synchronization results
        """
        if sync_options is None:
            sync_options = SyncOptions()
        
        start_time = timezone.now()
        errors = []
        
        try:
            # Create connection
            config = self._create_connection_config(mailbox.server)
            
            with IMAPClient.from_config(config) as client:
                # Use UID service for reliable operations
                uid_service = IMAPMailboxUIDService(client)
                
                # Select mailbox
                select_result = uid_service.select(mailbox.name)
                if not select_result.success:
                    raise Exception(f"Failed to select mailbox: {select_result.error_message}")
                
                # Get UIDs to sync
                if sync_options.full_sync:
                    uids = self._get_all_uids(uid_service)
                else:
                    uids = self._get_new_uids(uid_service, mailbox)
                
                # Apply limit if specified
                if sync_options.limit:
                    uids = uids[:sync_options.limit]
                
                if not uids:
                    execution_time = (timezone.now() - start_time).total_seconds()
                    return SyncResult(
                        success=True,
                        mailbox_name=mailbox.name,
                        total_emails=0,
                        new_emails=0,
                        updated_emails=0,
                        deleted_emails=0,
                        errors=[],
                        execution_time=execution_time
                    )
                
                # Sync emails in batches
                new_count, updated_count, deleted_count = self._sync_emails_in_batches(
                    uid_service, mailbox, uids, sync_options
                )
                
                # Update mailbox stats
                self._update_mailbox_stats(mailbox, uid_service)
                
                execution_time = (timezone.now() - start_time).total_seconds()
                
                return SyncResult(
                    success=True,
                    mailbox_name=mailbox.name,
                    total_emails=len(uids),
                    new_emails=new_count,
                    updated_emails=updated_count,
                    deleted_emails=deleted_count,
                    errors=errors,
                    execution_time=execution_time
                )
                
        except Exception as e:
            execution_time = (timezone.now() - start_time).total_seconds()
            error_msg = f"Sync failed for mailbox {mailbox.name}: {str(e)}"
            self.logger.error(error_msg)
            errors.append(error_msg)
            
            return SyncResult(
                success=False,
                mailbox_name=mailbox.name,
                total_emails=0,
                new_emails=0,
                updated_emails=0,
                deleted_emails=0,
                errors=errors,
                execution_time=execution_time
            )
    
    def sync_all_mailboxes(self, server, sync_options: SyncOptions = None) -> List[SyncResult]:
        """
        Synchronize all mailboxes for a server.
        
        Args:
            server: IMAPServer instance
            sync_options: Configuration options for sync
            
        Returns:
            List of SyncResult for each mailbox
        """
        if sync_options is None:
            sync_options = SyncOptions()
        
        results = []
        
        for mailbox in server.mailboxes.filter(is_active=True):
            result = self.sync_mailbox(mailbox, sync_options)
            results.append(result)
        
        return results
    
    def _create_connection_config(self, server) -> ConnectionConfig:
        """Create connection configuration from server."""
        return ConnectionConfig(
            host=server.host,
            username=server.username,
            password=server.get_decrypted_password(),
            port=server.port,
            use_ssl=server.use_ssl,
            timeout=server.timeout,
        )
    
    def _get_all_uids(self, uid_service: IMAPMailboxUIDService) -> List[str]:
        """Get all UIDs from the mailbox."""
        search_result = uid_service.uid_search(IMAPSearchCriteria.ALL)
        if not search_result.success:
            raise Exception(f"Failed to search for all UIDs: {search_result.error_message}")
        
        return search_result.affected_messages
    
    def _get_new_uids(self, uid_service: IMAPMailboxUIDService, mailbox) -> List[str]:
        """Get new UIDs since last sync."""
        from sage_mailbox.models import Email
        
        # Get last synced UID
        last_uid = Email.objects.filter(mailbox=mailbox).aggregate(
            max_uid=models.Max('uid')
        )['max_uid'] or 0
        
        if last_uid > 0:
            # Search for emails with UID greater than last synced
            search_criteria = f"UID {last_uid + 1}:*"
        else:
            # First sync - get all emails
            search_criteria = IMAPSearchCriteria.ALL
        
        search_result = uid_service.uid_search(search_criteria)
        if not search_result.success:
            raise Exception(f"Failed to search for new UIDs: {search_result.error_message}")
        
        return search_result.affected_messages
    
    def _sync_emails_in_batches(
        self, 
        uid_service: IMAPMailboxUIDService, 
        mailbox, 
        uids: List[str], 
        sync_options: SyncOptions
    ) -> Tuple[int, int, int]:
        """
        Sync emails in batches for better performance.
        
        Returns:
            Tuple of (new_count, updated_count, deleted_count)
        """
        from sage_mailbox.models import Email
        
        new_count = 0
        updated_count = 0
        deleted_count = 0
        
        # Create MessageSet from UIDs
        msg_set = MessageSet.from_uids([int(uid) for uid in uids], mailbox=mailbox.name)
        
        # Process in batches
        for batch in msg_set.iter_batches(batch_size=sync_options.batch_size):
            try:
                # Fetch emails from server
                fetch_result = uid_service.uid_fetch(batch, MessagePart.RFC822)
                if not fetch_result.success:
                    self.logger.error(f"Failed to fetch batch: {fetch_result.error_message}")
                    continue
                
                # Process each email in the batch
                fetched_emails = fetch_result.metadata.get('fetched_messages', [])
                
                for sage_email in fetched_emails:
                    try:
                        # Check if email exists
                        existing_email = Email.objects.filter(
                            mailbox=mailbox,
                            uid=sage_email.uid
                        ).first()
                        
                        if existing_email:
                            # Update existing email
                            if self._update_email_from_sage(existing_email, sage_email, sync_options):
                                updated_count += 1
                        else:
                            # Create new email
                            self._create_email_from_sage(sage_email, mailbox, sync_options)
                            new_count += 1
                            
                    except Exception as e:
                        self.logger.error(f"Failed to process email UID {sage_email.uid}: {e}")
                        continue
                
            except Exception as e:
                self.logger.error(f"Failed to process batch: {e}")
                continue
        
        return new_count, updated_count, deleted_count
    
    def _create_email_from_sage(
        self, 
        sage_email: SageEmailMessage, 
        mailbox, 
        sync_options: SyncOptions
    ) -> 'Email':
        """Create Django Email model from SageEmailMessage."""
        from sage_mailbox.models import Email, Attachment
        from django.core.files.base import ContentFile
        import hashlib
        
        # Create email without attachments first
        email = Email.objects.create(
            mailbox=mailbox,
            uid=sage_email.uid,
            message_id=sage_email.message_id,
            subject=sage_email.subject,
            from_address=str(sage_email.from_address) if sage_email.from_address else '',
            to_addresses=', '.join(str(addr) for addr in sage_email.to_address),  # Fixed: changed from .to_addresses to .to_address
            cc_addresses=', '.join(str(addr) for addr in sage_email.cc_address),  # Fixed: changed from .cc_addresses to .cc_address
            bcc_addresses=', '.join(str(addr) for addr in sage_email.bcc_address),  # Fixed: changed from .bcc_addresses to .bcc_address
            date=sage_email.date,
            size=sage_email.size,
            plain_body=sage_email.plain_body,
            html_body=sage_email.html_body,
            headers=sage_email.headers,
            raw_content=sage_email.raw if sync_options.sync_attachments else None,
            is_seen=Flag.SEEN in sage_email.flags if sync_options.sync_flags else False,
            is_answered=Flag.ANSWERED in sage_email.flags if sync_options.sync_flags else False,
            is_flagged=Flag.FLAGGED in sage_email.flags if sync_options.sync_flags else False,
            is_deleted=Flag.DELETED in sage_email.flags if sync_options.sync_flags else False,
            is_draft=Flag.DRAFT in sage_email.flags if sync_options.sync_flags else False,
            is_recent=Flag.RECENT in sage_email.flags if sync_options.sync_flags else False,
        )
        
        # Create attachments separately if enabled
        if sync_options.sync_attachments:
            for attachment in sage_email.attachments:
                # Create Django Attachment using the from_sage_attachment method
                django_attachment = Attachment.from_sage_attachment(attachment, email)
                
                # Save the attachment content to disk
                if attachment.payload:
                    content_file = ContentFile(
                        attachment.payload,
                        name=attachment.filename
                    )
                    django_attachment.file_path.save(
                        attachment.filename,
                        content_file,
                        save=False
                    )
                
                # Save the attachment
                django_attachment.save()
        
        return email
    
    def _update_email_from_sage(
        self, 
        email: 'Email', 
        sage_email: SageEmailMessage, 
        sync_options: SyncOptions
    ) -> bool:
        """
        Update Django Email model from SageEmailMessage.
        
        Returns:
            True if email was updated, False otherwise
        """
        updated = False
        
        # Update flags if enabled
        if sync_options.sync_flags:
            new_flags = {
                'is_seen': Flag.SEEN in sage_email.flags,
                'is_answered': Flag.ANSWERED in sage_email.flags,
                'is_flagged': Flag.FLAGGED in sage_email.flags,
                'is_deleted': Flag.DELETED in sage_email.flags,
                'is_draft': Flag.DRAFT in sage_email.flags,
                'is_recent': Flag.RECENT in sage_email.flags,
            }
            
            for flag_name, flag_value in new_flags.items():
                if getattr(email, flag_name) != flag_value:
                    setattr(email, flag_name, flag_value)
                    updated = True
        
        # Update content if missing
        if not email.raw_content and sage_email.raw:
            email.raw_content = sage_email.raw
            updated = True
        
        # Update headers if changed
        if email.headers != sage_email.headers:
            email.headers = sage_email.headers
            updated = True
        
        if updated:
            email.save()
        
        return updated
    
    def _update_mailbox_stats(self, mailbox, uid_service: IMAPMailboxUIDService):
        """Update mailbox statistics."""
        try:
            # Get mailbox statistics
            mailbox_service = IMAPMailboxService(uid_service.client)
            stats = mailbox_service.get_mailbox_statistics()
            
            # Update mailbox fields
            mailbox.message_count = stats.total_messages
            mailbox.unseen_count = stats.unread_messages
            mailbox.recent_count = stats.recent_messages
            mailbox.last_sync = timezone.now()
            mailbox.save()
            
        except Exception as e:
            self.logger.error(f"Failed to update mailbox stats: {e}")
    
    def sync_flags_for_mailbox(self, mailbox) -> Dict[str, int]:
        """
        Synchronize flags for all emails in a mailbox.
        
        Args:
            mailbox: Mailbox instance
            
        Returns:
            Dictionary with sync statistics
        """
        try:
            config = self._create_connection_config(mailbox.server)
            
            with IMAPClient.from_config(config) as client:
                uid_service = IMAPMailboxUIDService(client)
                flag_service = IMAPFlagService(uid_service)
                
                # Select mailbox
                select_result = uid_service.select(mailbox.name)
                if not select_result.success:
                    raise Exception(f"Failed to select mailbox: {select_result.error_message}")
                
                # Get all emails from database
                from sage_mailbox.models import Email
                emails = Email.objects.filter(mailbox=mailbox)
                
                updated_count = 0
                error_count = 0
                
                # Process emails in batches
                for email in emails:
                    try:
                        # Create MessageSet for this email
                        msg_set = MessageSet.from_uids([email.uid], mailbox=mailbox.name)
                        
                        # Fetch current flags from server
                        fetch_result = uid_service.uid_fetch(msg_set, MessagePart.FLAGS)
                        if not fetch_result.success:
                            error_count += 1
                            continue
                        
                        # Extract flags from response
                        fetched_emails = fetch_result.metadata.get('fetched_messages', [])
                        if fetched_emails:
                            sage_email = fetched_emails[0]
                            
                            # Update flags in database
                            flags_updated = False
                            if email.is_seen != (Flag.SEEN in sage_email.flags):
                                email.is_seen = Flag.SEEN in sage_email.flags
                                flags_updated = True
                            
                            if email.is_flagged != (Flag.FLAGGED in sage_email.flags):
                                email.is_flagged = Flag.FLAGGED in sage_email.flags
                                flags_updated = True
                            
                            if email.is_answered != (Flag.ANSWERED in sage_email.flags):
                                email.is_answered = Flag.ANSWERED in sage_email.flags
                                flags_updated = True
                            
                            if flags_updated:
                                email.save()
                                updated_count += 1
                        
                    except Exception as e:
                        self.logger.error(f"Failed to sync flags for email {email.uid}: {e}")
                        error_count += 1
                        continue
                
                return {
                    'total_emails': emails.count(),
                    'updated_emails': updated_count,
                    'error_count': error_count,
                }
                
        except Exception as e:
            self.logger.error(f"Failed to sync flags for mailbox {mailbox.name}: {e}")
            return {
                'total_emails': 0,
                'updated_emails': 0,
                'error_count': 1,
            }
    
    def cleanup_deleted_emails(self, mailbox) -> int:
        """
        Clean up emails that were deleted on the server.
        
        Args:
            mailbox: Mailbox instance
            
        Returns:
            Number of emails cleaned up
        """
        try:
            config = self._create_connection_config(mailbox.server)
            
            with IMAPClient.from_config(config) as client:
                uid_service = IMAPMailboxUIDService(client)
                
                # Select mailbox
                select_result = uid_service.select(mailbox.name)
                if not select_result.success:
                    raise Exception(f"Failed to select mailbox: {select_result.error_message}")
                
                # Get all UIDs from server
                server_uids = set(self._get_all_uids(uid_service))
                
                # Get all UIDs from database
                from sage_mailbox.models import Email
                db_uids = set(
                    Email.objects.filter(mailbox=mailbox).values_list('uid', flat=True)
                )
                
                # Find emails that exist in database but not on server
                deleted_uids = db_uids - {int(uid) for uid in server_uids}
                
                if deleted_uids:
                    # Delete emails from database
                    deleted_count = Email.objects.filter(
                        mailbox=mailbox,
                        uid__in=deleted_uids
                    ).delete()[0]
                    
                    self.logger.info(f"Cleaned up {deleted_count} deleted emails from {mailbox.name}")
                    return deleted_count
                
                return 0
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup deleted emails for {mailbox.name}: {e}")
            return 0


# Global service instance
email_sync_service = EmailSyncService() 