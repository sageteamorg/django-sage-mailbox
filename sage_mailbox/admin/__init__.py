"""
Admin configurations for sage_mailbox.

This package contains all Django admin configurations for the sage_mailbox application.
Admin classes are organized by their domain responsibilities.
"""

from .base import BaseModelAdmin
from ..forms import IMAPServerForm, SMTPServerForm, EmailForm, EmailComposeForm
from .server_admin import IMAPServerAdmin, SMTPServerAdmin
from .template_admin import EmailTemplateAdmin
from .mailbox_admin import MailboxAdmin
from .email_admin import EmailAdmin
from .attachment_admin import AttachmentAdmin, EmailFlagAdmin
from .site import MailboxAdminSite, mailbox_admin_site
from .actions import (
    # Email actions
    upload_eml_action,
    download_multiple_eml_action,
    sync_emails_action,
    full_sync_emails_action,
    export_email_data_action,
    get_email_statistics_action,
    search_by_sender_action,
    search_by_subject_action,
    
    # Mailbox actions
    clean_trash_action,
    
    # Flag actions
    mark_read_action,
    mark_unread_action,
    mark_flagged_action,
    mark_unflagged_action,
    move_to_trash_action,
    restore_from_trash_action,
    
    # Attachment actions
    cleanup_orphaned_attachments_action,
    verify_attachment_integrity_action,
    download_attachments_action,
    regenerate_checksums_action,
)

__all__ = [
    # Base classes
    'BaseModelAdmin',
    
    # Forms
    'IMAPServerForm',
    'SMTPServerForm',
    'EmailForm',
    'EmailComposeForm',
    
    # Admin classes
    'IMAPServerAdmin',
    'SMTPServerAdmin',
    'EmailTemplateAdmin',
    'MailboxAdmin',
    'EmailAdmin',
    'AttachmentAdmin',
    'EmailFlagAdmin',
    
    # Custom admin site
    'MailboxAdminSite',
    'mailbox_admin_site',
    
    # Actions
    'upload_eml_action',
    'download_multiple_eml_action',
    'sync_emails_action',
    'full_sync_emails_action',
    'export_email_data_action',
    'get_email_statistics_action',
    'search_by_sender_action',
    'search_by_subject_action',
    'clean_trash_action',
    'mark_read_action',
    'mark_unread_action',
    'mark_flagged_action',
    'mark_unflagged_action',
    'move_to_trash_action',
    'restore_from_trash_action',
    'cleanup_orphaned_attachments_action',
    'verify_attachment_integrity_action',
    'download_attachments_action',
    'regenerate_checksums_action',
] 