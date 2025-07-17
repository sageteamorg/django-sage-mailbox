"""
Proxy models for sage_mailbox.

This module contains proxy models that provide specialized views of the base models.
Proxy models inherit from the base models but provide different default querysets
and behaviors for specific use cases.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from .email import Email
from .mailbox import Mailbox


# Email proxy models
class InboxEmail(Email):
    """
    Proxy model for emails in the inbox.
    
    This model provides a specialized view of emails that are in the inbox folder.
    It includes only emails that are not deleted and are in the inbox mailbox.
    """
    
    class Meta:
        proxy = True
        verbose_name = _("Inbox Email")
        verbose_name_plural = _("Inbox Emails")
    
    def save(self, *args, **kwargs):
        # Ensure this email is not marked as deleted or in trash
        self.is_deleted = False
        self.is_in_trash = False
        super().save(*args, **kwargs)


class SentEmail(Email):
    """
    Proxy model for sent emails.
    
    This model provides a specialized view of emails that have been sent.
    It includes only emails that are marked as outgoing and have been sent.
    """
    
    class Meta:
        proxy = True
        verbose_name = _("Sent Email")
        verbose_name_plural = _("Sent Emails")
    
    def save(self, *args, **kwargs):
        # Ensure this email is marked as outgoing
        self.is_outgoing = True
        super().save(*args, **kwargs)


class DraftEmail(Email):
    """
    Proxy model for draft emails.
    
    This model provides a specialized view of emails that are drafts.
    It includes only emails that are marked as drafts and haven't been sent.
    """
    
    class Meta:
        proxy = True
        verbose_name = _("Draft Email")
        verbose_name_plural = _("Draft Emails")
    
    def save(self, *args, **kwargs):
        # Ensure this email is marked as draft
        self.is_draft = True
        self.send_status = 'draft'
        super().save(*args, **kwargs)


class TrashEmail(Email):
    """
    Proxy model for emails in trash.
    
    This model provides a specialized view of emails that are in the trash.
    It includes only emails that are marked as being in trash.
    """
    
    class Meta:
        proxy = True
        verbose_name = _("Trash Email")
        verbose_name_plural = _("Trash Emails")
    
    def save(self, *args, **kwargs):
        # Ensure this email is marked as in trash
        self.is_in_trash = True
        if not self.deleted_at:
            from django.utils import timezone
            self.deleted_at = timezone.now()
        super().save(*args, **kwargs)


class SpamEmail(Email):
    """
    Proxy model for spam emails.
    
    This model provides a specialized view of emails that are marked as spam.
    It includes only emails that are in spam/junk folders.
    """
    
    class Meta:
        proxy = True
        verbose_name = _("Spam Email")
        verbose_name_plural = _("Spam Emails")


class ImportantEmail(Email):
    """
    Proxy model for important emails.
    
    This model provides a specialized view of emails that are flagged as important.
    It includes only emails that have the flagged flag set.
    """
    
    class Meta:
        proxy = True
        verbose_name = _("Important Email")
        verbose_name_plural = _("Important Emails")
    
    def save(self, *args, **kwargs):
        # Ensure this email is flagged as important
        self.is_flagged = True
        super().save(*args, **kwargs)


class UnreadEmail(Email):
    """
    Proxy model for unread emails.
    
    This model provides a specialized view of emails that haven't been read yet.
    It includes only emails that don't have the seen flag set.
    """
    
    class Meta:
        proxy = True
        verbose_name = _("Unread Email")
        verbose_name_plural = _("Unread Emails")


class FlaggedEmail(Email):
    """
    Proxy model for flagged emails.
    
    This model provides a specialized view of emails that are flagged.
    It includes only emails that have the flagged flag set.
    """
    
    class Meta:
        proxy = True
        verbose_name = _("Flagged Email")
        verbose_name_plural = _("Flagged Emails")
    
    def save(self, *args, **kwargs):
        # Ensure this email is flagged
        self.is_flagged = True
        super().save(*args, **kwargs)


class AttachmentEmail(Email):
    """
    Proxy model for emails with attachments.
    
    This model provides a specialized view of emails that have attachments.
    It includes only emails that have at least one attachment.
    """
    
    class Meta:
        proxy = True
        verbose_name = _("Email with Attachments")
        verbose_name_plural = _("Emails with Attachments")


class RecentEmail(Email):
    """
    Proxy model for recent emails.
    
    This model provides a specialized view of emails that are recent.
    It includes only emails that have the recent flag set.
    """
    
    class Meta:
        proxy = True
        verbose_name = _("Recent Email")
        verbose_name_plural = _("Recent Emails")
    
    def save(self, *args, **kwargs):
        # Ensure this email is marked as recent
        self.is_recent = True
        super().save(*args, **kwargs)


class LargeEmail(Email):
    """
    Proxy model for large emails.
    
    This model provides a specialized view of emails that are large in size.
    It includes only emails that exceed a certain size threshold.
    """
    
    class Meta:
        proxy = True
        verbose_name = _("Large Email")
        verbose_name_plural = _("Large Emails")


# Mailbox proxy models
class InboxMailbox(Mailbox):
    """
    Proxy model for inbox mailboxes.
    
    This model provides a specialized view of mailboxes that are inbox folders.
    It includes only mailboxes that are designated as inbox folders.
    """
    
    class Meta:
        proxy = True
        verbose_name = _("Inbox Mailbox")
        verbose_name_plural = _("Inbox Mailboxes")


class SentMailbox(Mailbox):
    """
    Proxy model for sent mailboxes.
    
    This model provides a specialized view of mailboxes that contain sent emails.
    It includes only mailboxes that are designated as sent folders.
    """
    
    class Meta:
        proxy = True
        verbose_name = _("Sent Mailbox")
        verbose_name_plural = _("Sent Mailboxes")


class DraftMailbox(Mailbox):
    """
    Proxy model for draft mailboxes.
    
    This model provides a specialized view of mailboxes that contain draft emails.
    It includes only mailboxes that are designated as draft folders.
    """
    
    class Meta:
        proxy = True
        verbose_name = _("Draft Mailbox")
        verbose_name_plural = _("Draft Mailboxes")


class TrashMailbox(Mailbox):
    """
    Proxy model for trash mailboxes.
    
    This model provides a specialized view of mailboxes that contain deleted emails.
    It includes only mailboxes that are designated as trash folders.
    """
    
    class Meta:
        proxy = True
        verbose_name = _("Trash Mailbox")
        verbose_name_plural = _("Trash Mailboxes")


class SpamMailbox(Mailbox):
    """
    Proxy model for spam mailboxes.
    
    This model provides a specialized view of mailboxes that contain spam emails.
    It includes only mailboxes that are designated as spam/junk folders.
    """
    
    class Meta:
        proxy = True
        verbose_name = _("Spam Mailbox")
        verbose_name_plural = _("Spam Mailboxes")


class CustomFolderMailbox(Mailbox):
    """
    Proxy model for custom mailboxes.
    
    This model provides a specialized view of mailboxes that are custom folders
    created by users. It includes only mailboxes that are not default system folders.
    """
    
    class Meta:
        proxy = True
        verbose_name = _("Custom Folder Mailbox")
        verbose_name_plural = _("Custom Folder Mailboxes")
    
    def save(self, *args, **kwargs):
        # Ensure this mailbox is not marked as default
        self.is_default = False
        super().save(*args, **kwargs) 