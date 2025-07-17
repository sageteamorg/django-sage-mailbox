"""
Manager classes for sage_mailbox repository layer.

This module provides custom Manager classes with business logic
for email and mailbox operations.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.contrib.auth.models import User
from django.db import models, transaction
from django.utils import timezone

from sage_imap.helpers.enums import Flag, DefaultMailboxes, MailboxStatusItems, MessagePart
from sage_imap.helpers.search import IMAPSearchCriteria
from sage_imap.models.email import EmailMessage as SageEmailMessage
from sage_imap.models.email import Attachment as SageAttachment
from sage_imap.models.message import MessageSet
from sage_imap.services.client import IMAPClient
from sage_imap.services.folder import IMAPFolderService
from sage_imap.services.mailbox import IMAPMailboxService, IMAPMailboxUIDService
from sage_imap.services.flag import IMAPFlagService
from sage_imap.services.client import ConnectionConfig

from .queryset import EmailQuerySet, MailboxQuerySet

logger = logging.getLogger(__name__)


class MailboxManager(models.Manager):
    """Custom manager for Mailbox model."""
    
    def get_queryset(self):
        """Return custom queryset."""
        return MailboxQuerySet(self.model, using=self._db)
    
    def active(self):
        """Get active mailboxes."""
        return self.get_queryset().active()
    
    def for_user(self, user: User):
        """Get mailboxes for a specific user."""
        return self.get_queryset().for_user(user)
    
    def for_server(self, server):
        """Get mailboxes for a specific server."""
        return self.get_queryset().for_server(server)
    
    def get_or_create_default_mailboxes(self, server) -> List['Mailbox']:
        """Get or create default mailboxes for a server."""
        default_mailboxes = []
        
        for mailbox_name in DefaultMailboxes:
            mailbox, created = self.get_or_create(
                server=server,
                name=mailbox_name,
                defaults={
                    'display_name': mailbox_name.title(),
                    'is_default': True,
                }
            )
            default_mailboxes.append(mailbox)
            
            if created:
                logger.info(f"Created default mailbox: {mailbox_name} for server {server}")
        
        return default_mailboxes
    
    def sync_mailboxes_from_server(self, server) -> List['Mailbox']:
        """Synchronize mailboxes from IMAP server."""
        from sage_mailbox.models import IMAPServer
        
        # Create connection config
        logger.debug(f"Creating connection config for server: {server.name}")
        logger.debug(f"Host: {server.host}")
        logger.debug(f"Port: {server.port}")
        logger.debug(f"Username: {server.username}")
        logger.debug(f"Use SSL: {server.use_ssl}")
        logger.debug(f"Timeout: {server.timeout}")
        decrypted_password = server.get_decrypted_password()
        
        config = ConnectionConfig(
            host=server.host,
            username=server.username,
            password=decrypted_password,
            port=server.port,
            use_ssl=server.use_ssl,
            timeout=server.timeout,
        )
        
        mailboxes = []
        
        try:
            with IMAPClient.from_config(config) as client:
                # Get folder service
                folder_service = IMAPFolderService(client)
                
                # List all folders with fallback patterns
                folders = []
                try:
                    # Try default pattern first
                    folders = folder_service.list_folders()
                except Exception as e:
                    logger.warning(f"Failed to list folders with default pattern: {e}")
                    # Try alternative patterns for compatibility
                    for pattern in ["", "%", "*"]:
                        try:
                            logger.debug(f"Trying folder pattern: '{pattern}'")
                            folders = folder_service.list_folders(pattern=pattern)
                            logger.info(f"Successfully listed folders with pattern: '{pattern}'")
                            break
                        except Exception as pattern_error:
                            logger.debug(f"Pattern '{pattern}' failed: {pattern_error}")
                            continue
                    
                    if not folders:
                        logger.warning("All folder listing patterns failed, trying subscribed folders")
                        try:
                            folders = folder_service.list_subscribed_folders()
                        except Exception as sub_error:
                            logger.error(f"Failed to list subscribed folders: {sub_error}")
                            
                            # Last resort: try individual folder names
                            logger.warning("Trying individual common folder names")
                            common_folders = ["INBOX", "Sent", "Drafts", "Trash", "Spam", "Junk"]
                            for folder_name in common_folders:
                                try:
                                    # Try to select the folder to see if it exists
                                    mailbox_service = IMAPMailboxService(client)
                                    result = mailbox_service.select(folder_name)
                                    if result.success:
                                        folders.append({'name': folder_name, 'delimiter': '/'})
                                        logger.info(f"Found folder: {folder_name}")
                                except Exception as folder_error:
                                    logger.debug(f"Folder '{folder_name}' not found: {folder_error}")
                                    continue
                            
                            if not folders:
                                logger.error("All fallback methods failed")
                                raise Exception(f"Failed to list folders: {e}")
                
                if not folders:
                    logger.warning("No folders found, creating default INBOX")
                    folders = [{'name': 'INBOX', 'delimiter': '/'}]
                
                for folder_info in folders:
                    # Handle both FolderInfo objects and dictionary fallbacks
                    if hasattr(folder_info, 'name'):
                        # FolderInfo object
                        folder_name = folder_info.name
                        folder_delimiter = folder_info.delimiter
                    else:
                        # Dictionary fallback
                        folder_name = folder_info.get('name', '')
                        folder_delimiter = folder_info.get('delimiter', '/')
                    
                    if not folder_name:
                        continue
                    
                    # Get or create mailbox
                    mailbox, created = self.get_or_create(
                        server=server,
                        name=folder_name,
                        defaults={
                            'display_name': folder_name,
                            'delimiter': folder_delimiter,
                            'is_default': folder_name in [mb.value for mb in DefaultMailboxes],
                        }
                    )
                    
                    mailboxes.append(mailbox)
                    
                    if created:
                        logger.info(f"Created mailbox: {folder_name} for server {server}")
                
                # Update last sync time
                self.filter(server=server).update(last_sync=timezone.now())
                
        except Exception as e:
            logger.error(f"Failed to sync mailboxes from server {server}: {e}")
            raise
        
        return mailboxes
    
    def update_mailbox_stats(self, mailbox) -> Dict[str, Any]:
        """Update mailbox statistics using full sage_imap capabilities."""
        from sage_mailbox.models import IMAPServer
        
        server = mailbox.server
        config = ConnectionConfig(
            host=server.host,
            username=server.username,
            password=server.get_decrypted_password(),
            port=server.port,
            use_ssl=server.use_ssl,
            timeout=server.timeout,
        )
        
        try:
            with IMAPClient.from_config(config) as client:
                mailbox_service = IMAPMailboxService(client)
                
                # Select mailbox
                select_result = mailbox_service.select(mailbox.name)
                if not select_result.success:
                    raise Exception(f"Failed to select mailbox: {select_result.error_message}")
                
                # Get comprehensive mailbox statistics
                stats = mailbox_service.get_mailbox_statistics()
                
                # Update mailbox fields
                mailbox.message_count = stats.total_messages
                mailbox.unseen_count = stats.unread_messages
                mailbox.recent_count = stats.recent_messages
                mailbox.last_sync = timezone.now()
                
                # Get additional status info for UIDVALIDITY and UIDNEXT
                status_result = mailbox_service.status(
                    mailbox.name,
                    MailboxStatusItems.UIDVALIDITY,
                    MailboxStatusItems.UIDNEXT
                )
                
                if status_result.success:
                    status_data = status_result.metadata.get("status_response", [])
                    for item in status_data:
                        if isinstance(item, bytes):
                            item = item.decode()
                        if "UIDVALIDITY" in item:
                            import re
                            match = re.search(r"UIDVALIDITY (\d+)", item)
                            if match:
                                mailbox.uidvalidity = int(match.group(1))
                        if "UIDNEXT" in item:
                            import re
                            match = re.search(r"UIDNEXT (\d+)", item)
                            if match:
                                mailbox.uidnext = int(match.group(1))
                
                mailbox.save()
                
                logger.info(f"Updated stats for mailbox: {mailbox}")
                
                return {
                    'message_count': mailbox.message_count,
                    'unseen_count': mailbox.unseen_count,
                    'recent_count': mailbox.recent_count,
                    'uidvalidity': mailbox.uidvalidity,
                    'uidnext': mailbox.uidnext,
                }
                
        except Exception as e:
            logger.error(f"Failed to update stats for mailbox {mailbox}: {e}")
            raise
    
    def needs_sync(self, hours: int = 24):
        """Get mailboxes that need synchronization."""
        return self.get_queryset().needs_sync(hours)
    
    def recently_synced(self, hours: int = 1):
        """Get recently synchronized mailboxes."""
        return self.get_queryset().recently_synced(hours)


class EmailManager(models.Manager):
    """Custom manager for Email model."""
    
    def get_queryset(self):
        """Return custom queryset."""
        return EmailQuerySet(self.model, using=self._db)
    
    def active(self):
        """Get active emails."""
        return self.get_queryset().active()
    
    def for_user(self, user: User):
        """Get emails for a specific user."""
        return self.get_queryset().for_user(user)
    
    def for_mailbox(self, mailbox):
        """Get emails for a specific mailbox."""
        return self.get_queryset().for_mailbox(mailbox)
    
    def sync_emails_from_server(
        self, 
        mailbox, 
        full_sync: bool = False,
        limit: Optional[int] = None
    ) -> Tuple[int, int]:
        """
        Synchronize emails from IMAP server using full sage_imap capabilities.
        
        Args:
            mailbox: Mailbox to sync
            full_sync: If True, sync all emails. If False, sync only new emails.
            limit: Maximum number of emails to sync
            
        Returns:
            Tuple of (created_count, updated_count)
        """
        from sage_mailbox.models import IMAPServer
        
        server = mailbox.server
        config = ConnectionConfig(
            host=server.host,
            username=server.username,
            password=server.get_decrypted_password(),
            port=server.port,
            use_ssl=server.use_ssl,
            timeout=server.timeout,
        )
        
        created_count = 0
        updated_count = 0
        
        try:
            with IMAPClient.from_config(config) as client:
                # Use UID service for reliable operations
                uid_service = IMAPMailboxUIDService(client)
                
                # Select mailbox
                select_result = uid_service.select(mailbox.name)
                if not select_result.success:
                    raise Exception(f"Failed to select mailbox: {select_result.error_message}")
                
                # Determine search criteria
                if full_sync:
                    search_criteria = IMAPSearchCriteria.ALL
                else:
                    # Get only new emails since last sync
                    last_uid = self.filter(mailbox=mailbox).aggregate(
                        models.Max('uid')
                    )['uid__max'] or 0
                    
                    if last_uid > 0:
                        search_criteria = f"UID {last_uid + 1}:*"
                    else:
                        search_criteria = IMAPSearchCriteria.ALL
                
                # Search for emails using UID
                search_result = uid_service.uid_search(search_criteria)
                if not search_result.success:
                    raise Exception(f"Failed to search emails: {search_result.error_message}")
                
                uids = search_result.affected_messages
                
                # Limit number of UIDs if specified
                if limit:
                    uids = uids[:limit]
                
                if not uids:
                    logger.info(f"No new emails found for mailbox {mailbox}")
                    return created_count, updated_count

                logger.info(f"Syncing {len(uids)} emails for mailbox {mailbox}")
                logger.debug(f"UIDs to sync: {uids[:10]}...")  # Show first 10 UIDs
                
                # Process UIDs directly in batches (bypassing MessageSet batching issue)
                batch_size = 50
                uid_batches = [uids[i:i + batch_size] for i in range(0, len(uids), batch_size)]
                logger.debug(f"Created {len(uid_batches)} batches for processing")
                
                for i, uid_batch in enumerate(uid_batches):
                    try:
                        logger.debug(f"Processing batch {i+1}/{len(uid_batches)} with {len(uid_batch)} UIDs")
                        
                        # Create MessageSet for this batch
                        batch_msg_set = MessageSet.from_uids([int(uid) for uid in uid_batch])
                        
                        # Fetch full email content
                        fetch_result = uid_service.uid_fetch(batch_msg_set, MessagePart.RFC822)
                        if not fetch_result.success:
                            logger.error(f"Failed to fetch batch: {fetch_result.error_message}")
                            continue
                        
                        # Process fetched emails
                        fetched_emails = fetch_result.metadata.get('fetched_messages', [])
                        logger.debug(f"Successfully fetched {len(fetched_emails)} emails from batch")
                        
                        if not fetched_emails:
                            logger.warning(f"No emails in fetched_messages, checking fetch_result structure: {fetch_result.metadata.keys()}")
                            # Try alternative ways to get the emails
                            if hasattr(fetch_result, 'data'):
                                logger.debug(f"fetch_result.data type: {type(fetch_result.data)}")
                                if isinstance(fetch_result.data, list):
                                    fetched_emails = fetch_result.data
                                    logger.debug(f"Using fetch_result.data: {len(fetched_emails)} emails")
                        
                        for sage_email in fetched_emails:
                            try:
                                logger.debug(f"Processing email UID {sage_email.uid}: {sage_email.subject}")
                                
                                # Check if email already exists
                                existing_email = self.filter(
                                    mailbox=mailbox,
                                    uid=sage_email.uid
                                ).first()
                                
                                if existing_email:
                                    # Update existing email
                                    self._update_email_from_sage(existing_email, sage_email)
                                    updated_count += 1
                                    logger.debug(f"Updated existing email UID {sage_email.uid}")
                                else:
                                    # Create new email
                                    self._create_email_from_sage(sage_email, mailbox)
                                    created_count += 1
                                    logger.debug(f"Created new email UID {sage_email.uid}")
                                    
                            except Exception as e:
                                logger.error(f"Failed to process email UID {sage_email.uid}: {e}")
                                import traceback
                                logger.error(traceback.format_exc())
                                continue
                    
                    except Exception as e:
                        logger.error(f"Failed to process batch: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        continue
                
                # Update mailbox last sync time
                mailbox.last_sync = timezone.now()
                mailbox.save()
                
                logger.info(
                    f"Sync completed for mailbox {mailbox}: "
                    f"created={created_count}, updated={updated_count}"
                )
                
        except Exception as e:
            logger.error(f"Failed to sync emails for mailbox {mailbox}: {e}")
            raise
        
        return created_count, updated_count
    
    def _create_email_from_sage(self, sage_email: SageEmailMessage, mailbox) -> 'Email':
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
            to_addresses=', '.join(str(addr) for addr in sage_email.to_address),  # Changed from .to_addresses to .to_address
            cc_addresses=', '.join(str(addr) for addr in sage_email.cc_address),  # Changed from .cc_addresses to .cc_address
            bcc_addresses=', '.join(str(addr) for addr in sage_email.bcc_address),  # Changed from .bcc_addresses to .bcc_address
            date=sage_email.date,
            size=sage_email.size,
            plain_body=sage_email.plain_body,
            html_body=sage_email.html_body,
            headers=sage_email.headers,
            raw_content=sage_email.raw,
            is_seen=Flag.SEEN in sage_email.flags,
            is_answered=Flag.ANSWERED in sage_email.flags,
            is_flagged=Flag.FLAGGED in sage_email.flags,
            is_deleted=Flag.DELETED in sage_email.flags,
            is_draft=Flag.DRAFT in sage_email.flags,
            is_recent=Flag.RECENT in sage_email.flags,
        )
        
        # Create attachments separately
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
    
    def _update_email_from_sage(self, email: 'Email', sage_email: SageEmailMessage):
        """Update Django Email model from SageEmailMessage."""
        # Update flags
        email.is_seen = Flag.SEEN in sage_email.flags
        email.is_answered = Flag.ANSWERED in sage_email.flags
        email.is_flagged = Flag.FLAGGED in sage_email.flags
        email.is_deleted = Flag.DELETED in sage_email.flags
        email.is_draft = Flag.DRAFT in sage_email.flags
        email.is_recent = Flag.RECENT in sage_email.flags
        
        # Update content if needed
        if not email.raw_content and sage_email.raw:
            email.raw_content = sage_email.raw
        
        email.save()
    
    def mark_as_read(self, emails_queryset):
        """Mark emails as read both in database and on server using sage_imap bulk operations."""
        return self._bulk_update_email_flags(emails_queryset, Flag.SEEN, True, 'is_seen')
    
    def mark_as_unread(self, emails_queryset):
        """Mark emails as unread both in database and on server using sage_imap bulk operations."""
        return self._bulk_update_email_flags(emails_queryset, Flag.SEEN, False, 'is_seen')
    
    def mark_as_flagged(self, emails_queryset):
        """Mark emails as flagged both in database and on server using sage_imap bulk operations."""
        return self._bulk_update_email_flags(emails_queryset, Flag.FLAGGED, True, 'is_flagged')
    
    def mark_as_unflagged(self, emails_queryset):
        """Mark emails as unflagged both in database and on server using sage_imap bulk operations."""
        return self._bulk_update_email_flags(emails_queryset, Flag.FLAGGED, False, 'is_flagged')
    
    def _bulk_update_email_flags(self, emails_queryset, flag: Flag, value: bool, db_field: str):
        """Bulk update email flags on server and database using sage_imap bulk operations."""
        # Group emails by mailbox to minimize IMAP connections
        emails_by_mailbox = {}
        
        for email in emails_queryset:
            mailbox = email.mailbox
            if mailbox not in emails_by_mailbox:
                emails_by_mailbox[mailbox] = []
            emails_by_mailbox[mailbox].append(email)
        
        total_updated = 0
        
        # Process each mailbox separately
        for mailbox, emails in emails_by_mailbox.items():
            try:
                # Update on server first
                updated_count = self._bulk_update_flags_on_server(emails, flag, value)
                
                # Update in database only if server operation succeeded
                if updated_count > 0:
                    email_ids = [email.id for email in emails]
                    self.filter(id__in=email_ids).update(**{db_field: value})
                    total_updated += updated_count
                    
                    logger.info(f"Bulk updated {updated_count} emails in mailbox {mailbox.name}")
                
            except Exception as e:
                logger.error(f"Failed to bulk update flags for mailbox {mailbox.name}: {e}")
                continue
        
        return total_updated
    
    def _bulk_update_flags_on_server(self, emails, flag: Flag, value: bool):
        """Bulk update flags on server using sage_imap UID operations."""
        if not emails:
            return 0
        
        # All emails should be from the same mailbox
        mailbox = emails[0].mailbox
        server = mailbox.server
        
        config = ConnectionConfig(
            host=server.host,
            username=server.username,
            password=server.get_decrypted_password(),
            port=server.port,
            use_ssl=server.use_ssl,
            timeout=server.timeout,
        )
        
        with IMAPClient.from_config(config) as client:
            uid_service = IMAPMailboxUIDService(client)
            
            # Select mailbox
            select_result = uid_service.select(mailbox.name)
            if not select_result.success:
                raise Exception(f"Failed to select mailbox: {select_result.error_message}")
            
            # Collect all UIDs
            uids = [email.uid for email in emails]
            
            # Verify UIDs exist in the mailbox (batch verification)
            search_result = uid_service.uid_search(f"UID {','.join(str(uid) for uid in uids)}")
            if not search_result.success:
                raise Exception(f"Failed to verify UIDs: {search_result.error_message}")
            
            # Only process UIDs that exist on the server
            existing_uids = [int(uid) for uid in search_result.affected_messages]
            valid_uids = [uid for uid in uids if uid in existing_uids]
            
            if not valid_uids:
                logger.warning(f"No valid UIDs found for bulk operation in mailbox {mailbox.name}")
                return 0
            
            # Convert UIDs to comma-separated string for bulk operation
            uid_string = ','.join(str(uid) for uid in valid_uids)
            
            logger.debug(f"Bulk updating flag {flag.value} to {value} for {len(valid_uids)} emails in mailbox {mailbox.name}")
            
            # Use bulk UID STORE command
            try:
                if value:
                    # Add flag using bulk UID STORE
                    status, response = client.uid("STORE", uid_string, "+FLAGS", flag.value)
                else:
                    # Remove flag using bulk UID STORE
                    status, response = client.uid("STORE", uid_string, "-FLAGS", flag.value)
                
                if status != "OK":
                    raise Exception(f"Bulk STORE command failed: {status} {response}")
                
                logger.info(f"Successfully bulk updated flag {flag.value} to {value} for {len(valid_uids)} emails")
                return len(valid_uids)
                
            except Exception as e:
                raise Exception(f"Failed to bulk update flag {flag.value}: {str(e)}")
    
    def move_to_trash(self, emails_queryset):
        """Move emails to trash using sage_imap bulk operations."""
        return self._bulk_move_emails(emails_queryset, 'trash')
    
    def restore_from_trash(self, emails_queryset):
        """Restore emails from trash using sage_imap bulk operations."""
        return self._bulk_move_emails(emails_queryset, 'restore')
    
    def _bulk_move_emails(self, emails_queryset, operation: str):
        """Bulk move emails using sage_imap operations."""
        # Group emails by mailbox
        emails_by_mailbox = {}
        
        for email in emails_queryset:
            mailbox = email.mailbox
            if mailbox not in emails_by_mailbox:
                emails_by_mailbox[mailbox] = []
            emails_by_mailbox[mailbox].append(email)
        
        total_updated = 0
        
        # Process each mailbox separately
        for mailbox, emails in emails_by_mailbox.items():
            try:
                if operation == 'trash':
                    # Find trash mailbox
                    trash_mailbox = mailbox.server.mailboxes.filter(
                        name=DefaultMailboxes.TRASH
                    ).first()
                    
                    if not trash_mailbox:
                        logger.warning(f"No trash mailbox found for server {mailbox.server}")
                        continue
                    
                    # Move emails to trash on server
                    moved_count = self._bulk_move_emails_on_server(emails, trash_mailbox)
                    
                    if moved_count > 0:
                        # Update database
                        email_ids = [email.id for email in emails]
                        self.filter(id__in=email_ids).update(
                            original_mailbox=mailbox,
                            mailbox=trash_mailbox,
                            is_in_trash=True,
                            deleted_at=timezone.now()
                        )
                        total_updated += moved_count
                
                elif operation == 'restore':
                    # Group by original mailbox
                    restore_groups = {}
                    for email in emails:
                        if email.original_mailbox:
                            orig_mailbox = email.original_mailbox
                            if orig_mailbox not in restore_groups:
                                restore_groups[orig_mailbox] = []
                            restore_groups[orig_mailbox].append(email)
                    
                    # Restore to original mailboxes
                    for orig_mailbox, restore_emails in restore_groups.items():
                        moved_count = self._bulk_move_emails_on_server(restore_emails, orig_mailbox)
                        
                        if moved_count > 0:
                            # Update database
                            email_ids = [email.id for email in restore_emails]
                            self.filter(id__in=email_ids).update(
                                mailbox=orig_mailbox,
                                original_mailbox=None,
                                is_in_trash=False,
                                deleted_at=None
                            )
                            total_updated += moved_count
                
            except Exception as e:
                logger.error(f"Failed to bulk {operation} emails for mailbox {mailbox.name}: {e}")
                continue
        
        return total_updated
    
    def _bulk_move_emails_on_server(self, emails, target_mailbox):
        """Bulk move emails to target mailbox on server using sage_imap."""
        if not emails:
            return 0
        
        # All emails should be from the same source mailbox
        source_mailbox = emails[0].mailbox
        server = source_mailbox.server
        
        config = ConnectionConfig(
            host=server.host,
            username=server.username,
            password=server.get_decrypted_password(),
            port=server.port,
            use_ssl=server.use_ssl,
            timeout=server.timeout,
        )
        
        with IMAPClient.from_config(config) as client:
            uid_service = IMAPMailboxUIDService(client)
            
            # Select source mailbox
            select_result = uid_service.select(source_mailbox.name)
            if not select_result.success:
                raise Exception(f"Failed to select source mailbox: {select_result.error_message}")
            
            # Collect all UIDs
            uids = [email.uid for email in emails]
            
            # Verify UIDs exist in the mailbox
            search_result = uid_service.uid_search(f"UID {','.join(str(uid) for uid in uids)}")
            if not search_result.success:
                raise Exception(f"Failed to verify UIDs: {search_result.error_message}")
            
            # Only process UIDs that exist on the server
            existing_uids = [int(uid) for uid in search_result.affected_messages]
            valid_uids = [uid for uid in uids if uid in existing_uids]
            
            if not valid_uids:
                logger.warning(f"No valid UIDs found for bulk move in mailbox {source_mailbox.name}")
                return 0
            
            # Convert UIDs to comma-separated string for bulk operation
            uid_string = ','.join(str(uid) for uid in valid_uids)
            
            logger.debug(f"Bulk moving {len(valid_uids)} emails from {source_mailbox.name} to {target_mailbox.name}")
            
            # Use bulk UID COPY and UID STORE operations
            try:
                # Copy to destination
                status, response = client.uid("COPY", uid_string, target_mailbox.name)
                if status != "OK":
                    raise Exception(f"Bulk COPY command failed: {status} {response}")
                
                # Mark as deleted in source
                status, response = client.uid("STORE", uid_string, "+FLAGS", Flag.DELETED.value)
                if status != "OK":
                    raise Exception(f"Bulk STORE command failed: {status} {response}")
                
                # Expunge to permanently remove from source
                client.expunge()
                
                logger.info(f"Successfully bulk moved {len(valid_uids)} emails")
                return len(valid_uids)
                
            except Exception as e:
                raise Exception(f"Failed to bulk move emails: {str(e)}")
    
    def permanent_delete(self, emails_queryset):
        """Permanently delete emails from server and database using sage_imap bulk operations."""
        # Group emails by mailbox
        emails_by_mailbox = {}
        
        for email in emails_queryset:
            mailbox = email.mailbox
            if mailbox not in emails_by_mailbox:
                emails_by_mailbox[mailbox] = []
            emails_by_mailbox[mailbox].append(email)
        
        total_deleted = 0
        
        # Process each mailbox separately
        for mailbox, emails in emails_by_mailbox.items():
            try:
                # Delete from server first
                deleted_count = self._bulk_delete_emails_on_server(emails)
                
                if deleted_count > 0:
                    # Delete from database
                    email_ids = [email.id for email in emails]
                    self.filter(id__in=email_ids).delete()
                    total_deleted += deleted_count
                    
                    logger.info(f"Bulk deleted {deleted_count} emails from mailbox {mailbox.name}")
                
            except Exception as e:
                logger.error(f"Failed to bulk delete emails for mailbox {mailbox.name}: {e}")
                continue
        
        return total_deleted
    
    def _bulk_delete_emails_on_server(self, emails):
        """Bulk delete emails from server using sage_imap."""
        if not emails:
            return 0
        
        # All emails should be from the same mailbox
        mailbox = emails[0].mailbox
        server = mailbox.server
        
        config = ConnectionConfig(
            host=server.host,
            username=server.username,
            password=server.get_decrypted_password(),
            port=server.port,
            use_ssl=server.use_ssl,
            timeout=server.timeout,
        )
        
        with IMAPClient.from_config(config) as client:
            uid_service = IMAPMailboxUIDService(client)
            
            # Select mailbox
            select_result = uid_service.select(mailbox.name)
            if not select_result.success:
                raise Exception(f"Failed to select mailbox: {select_result.error_message}")
            
            # Collect all UIDs
            uids = [email.uid for email in emails]
            
            # Verify UIDs exist in the mailbox
            search_result = uid_service.uid_search(f"UID {','.join(str(uid) for uid in uids)}")
            if not search_result.success:
                raise Exception(f"Failed to verify UIDs: {search_result.error_message}")
            
            # Only process UIDs that exist on the server
            existing_uids = [int(uid) for uid in search_result.affected_messages]
            valid_uids = [uid for uid in uids if uid in existing_uids]
            
            if not valid_uids:
                logger.warning(f"No valid UIDs found for bulk delete in mailbox {mailbox.name}")
                return 0
            
            # Convert UIDs to comma-separated string for bulk operation
            uid_string = ','.join(str(uid) for uid in valid_uids)
            
            logger.debug(f"Bulk deleting {len(valid_uids)} emails from mailbox {mailbox.name}")
            
            # Use bulk UID STORE to mark as deleted, then expunge
            try:
                # Mark as deleted
                status, response = client.uid("STORE", uid_string, "+FLAGS", Flag.DELETED.value)
                if status != "OK":
                    raise Exception(f"Bulk STORE command failed: {status} {response}")
                
                # Expunge to permanently remove
                client.expunge()
                
                logger.info(f"Successfully bulk deleted {len(valid_uids)} emails")
                return len(valid_uids)
                
            except Exception as e:
                raise Exception(f"Failed to bulk delete emails: {str(e)}")
    
    def upload_eml_file(self, mailbox, eml_content: bytes) -> 'Email':
        """Upload .eml file to mailbox using sage_imap."""
        from sage_mailbox.models import Email
        
        # Parse EML content
        sage_email = SageEmailMessage.read_from_eml_bytes(eml_content)
        
        # Upload to server
        server = mailbox.server
        config = ConnectionConfig(
            host=server.host,
            username=server.username,
            password=server.get_decrypted_password(),
            port=server.port,
            use_ssl=server.use_ssl,
            timeout=server.timeout,
        )
        
        with IMAPClient.from_config(config) as client:
            mailbox_service = IMAPMailboxService(client)
            
            # Select mailbox
            select_result = mailbox_service.select(mailbox.name)
            if not select_result.success:
                raise Exception(f"Failed to select mailbox: {select_result.error_message}")
            
            # Upload email
            upload_result = mailbox_service.bulk_upload(
                mailbox.name,
                [sage_email],
                flags=sage_email.flags
            )
            
            if not upload_result.success:
                raise Exception(f"Failed to upload email: {upload_result.error_message}")
            
            # Create email in database
            email = self._create_email_from_sage(sage_email, mailbox)
            
            return email
    
    def download_as_eml(self, email) -> bytes:
        """Download email as .eml file using sage_imap UID operations directly."""
        if email.raw_content:
            return email.raw_content
        
        # Fetch from server if not available locally
        server = email.mailbox.server
        config = ConnectionConfig(
            host=server.host,
            username=server.username,
            password=server.get_decrypted_password(),
            port=server.port,
            use_ssl=server.use_ssl,
            timeout=server.timeout,
        )
        
        with IMAPClient.from_config(config) as client:
            uid_service = IMAPMailboxUIDService(client)
            
            # Select mailbox
            select_result = uid_service.select(email.mailbox.name)
            if not select_result.success:
                raise Exception(f"Failed to select mailbox: {select_result.error_message}")
            
            # Verify the UID exists in the mailbox first
            search_result = uid_service.uid_search(f"UID {email.uid}")
            if not search_result.success or not search_result.affected_messages:
                raise Exception(f"UID {email.uid} not found in mailbox {email.mailbox.name}")
            
            # Use UID FETCH command directly instead of MessageSet
            try:
                status, data = client.uid("FETCH", str(email.uid), "(RFC822)")
                
                if status != "OK":
                    raise Exception(f"FETCH command failed: {status} {data}")
                
                # Extract raw content from response
                if data and len(data) > 0:
                    for response_item in data:
                        if isinstance(response_item, tuple) and len(response_item) > 1:
                            # The raw content is typically in the second element
                            raw_content = response_item[1]
                            if isinstance(raw_content, bytes):
                                # Update email with raw content
                                email.raw_content = raw_content
                                email.save()
                                
                                return raw_content
                
                raise Exception("No email content received from server")
                
            except Exception as e:
                raise Exception(f"Failed to fetch email: {str(e)}")
    
    def search_emails(self, query: str, mailbox=None):
        """Search emails with full-text search."""
        queryset = self.get_queryset()
        
        if mailbox:
            queryset = queryset.for_mailbox(mailbox)
        
        return queryset.search(query)
    
    def get_email_thread(self, email):
        """Get all emails in the same thread."""
        if email.message_id:
            return self.get_queryset().get_thread_emails(email.message_id)
        return self.none()
    
    def clean_trash(self, mailbox, days_old: int = 30):
        """Clean trash by permanently deleting old emails."""
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        trash_emails = self.filter(
            mailbox=mailbox,
            is_in_trash=True,
            deleted_at__lt=cutoff_date
        )
        
        return self.permanent_delete(trash_emails)
    
    def bulk_operations(self, emails_queryset, operation: str, **kwargs):
        """Perform bulk operations on emails."""
        operations = {
            'mark_read': self.mark_as_read,
            'mark_unread': self.mark_as_unread,
            'mark_flagged': self.mark_as_flagged,
            'mark_unflagged': self.mark_as_unflagged,
            'move_to_trash': self.move_to_trash,
            'restore_from_trash': self.restore_from_trash,
            'permanent_delete': self.permanent_delete,
        }
        
        if operation in operations:
            return operations[operation](emails_queryset)
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    def get_statistics(self, mailbox=None, user=None):
        """Get email statistics."""
        queryset = self.get_queryset()
        
        if mailbox:
            queryset = queryset.for_mailbox(mailbox)
        elif user:
            queryset = queryset.for_user(user)
        
        return queryset.aggregate(
            total_emails=models.Count('id'),
            unread_emails=models.Count('id', filter=models.Q(is_seen=False)),
            flagged_emails=models.Count('id', filter=models.Q(is_flagged=True)),
            total_size=models.Sum('size'),
            avg_size=models.Avg('size'),
            latest_email=models.Max('date'),
            oldest_email=models.Min('date'),
        ) 