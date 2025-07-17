"""
Admin actions for sage_mailbox.

This package contains all Django admin actions for the sage_mailbox application.
Actions are organized by their domain responsibilities.
"""

from .email_actions import (
    upload_eml_action,
    download_multiple_eml_action,
    sync_emails_action,
    full_sync_emails_action,
    export_email_data_action,
    get_email_statistics_action,
    search_by_sender_action,
    search_by_subject_action,
)
from .mailbox_actions import (
    clean_trash_action,
)
from .flag_actions import (
    bulk_flag_action,
    mark_read_action,
    mark_unread_action,
    mark_flagged_action,
    mark_unflagged_action,
    move_to_trash_action,
    restore_from_trash_action,
)
from .attachment_actions import (
    cleanup_orphaned_attachments_action,
    verify_attachment_integrity_action,
    download_attachments_action,
    regenerate_checksums_action,
)

__all__ = [
    'upload_eml_action',
    'download_multiple_eml_action',
    'sync_emails_action',
    'full_sync_emails_action',
    'export_email_data_action',
    'get_email_statistics_action',
    'search_by_sender_action',
    'search_by_subject_action',
    'clean_trash_action',
    'bulk_flag_action',
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