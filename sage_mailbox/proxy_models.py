"""
Proxy models for sage_mailbox.

This module provides proxy models for different IMAP folders/directories
to enable specialized admin interfaces and filtering capabilities.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from .models import Email, Mailbox
from .repository.queryset import EmailQuerySet


class InboxEmail(Email):
    """
    Proxy model for emails in the INBOX folder.
    
    This model represents emails specifically from the INBOX folder,
    allowing for specialized admin interfaces and filtering.
    """
    
    class Meta:
        proxy = True
        verbose_name = _('Inbox Email')
        verbose_name_plural = _('Inbox Emails')
        
    objects = EmailQuerySet.as_manager()
    
    def save(self, *args, **kwargs):
        """Override save to ensure folder is set correctly."""
        if not self.folder:
            self.folder = 'INBOX'
        super().save(*args, **kwargs)
        
    @classmethod
    def get_queryset(cls):
        """Get queryset filtered to INBOX emails only."""
        return super().get_queryset().filter(
            models.Q(folder='INBOX') | 
            models.Q(folder__iexact='inbox') |
            models.Q(folder__isnull=True)  # Default to INBOX if no folder
        )


class SentEmail(Email):
    """
    Proxy model for emails in the Sent folder.
    
    This model represents emails from sent folders,
    allowing for specialized management of sent emails.
    """
    
    class Meta:
        proxy = True
        verbose_name = _('Sent Email')
        verbose_name_plural = _('Sent Emails')
        
    objects = EmailQuerySet.as_manager()
    
    def save(self, *args, **kwargs):
        """Override save to ensure folder is set correctly."""
        if not self.folder:
            self.folder = 'Sent'
        super().save(*args, **kwargs)
        
    @classmethod
    def get_queryset(cls):
        """Get queryset filtered to Sent emails only."""
        return super().get_queryset().filter(
            models.Q(folder='Sent') | 
            models.Q(folder='SENT') |
            models.Q(folder__icontains='sent') |
            models.Q(folder__icontains='Sent Items')
        )


class DraftEmail(Email):
    """
    Proxy model for emails in the Drafts folder.
    
    This model represents draft emails,
    allowing for specialized management of draft emails.
    """
    
    class Meta:
        proxy = True
        verbose_name = _('Draft Email')
        verbose_name_plural = _('Draft Emails')
        
    objects = EmailQuerySet.as_manager()
    
    def save(self, *args, **kwargs):
        """Override save to ensure folder is set correctly."""
        if not self.folder:
            self.folder = 'Drafts'
        super().save(*args, **kwargs)
        
    @classmethod
    def get_queryset(cls):
        """Get queryset filtered to Draft emails only."""
        return super().get_queryset().filter(
            models.Q(folder='Drafts') | 
            models.Q(folder='DRAFTS') |
            models.Q(folder__icontains='draft')
        )


class TrashEmail(Email):
    """
    Proxy model for emails in the Trash/Deleted folder.
    
    This model represents deleted emails,
    allowing for specialized management of trashed emails.
    """
    
    class Meta:
        proxy = True
        verbose_name = _('Trash Email')
        verbose_name_plural = _('Trash Emails')
        
    objects = EmailQuerySet.as_manager()
    
    def save(self, *args, **kwargs):
        """Override save to ensure folder is set correctly."""
        if not self.folder:
            self.folder = 'Trash'
        super().save(*args, **kwargs)
        
    @classmethod
    def get_queryset(cls):
        """Get queryset filtered to Trash emails only."""
        return super().get_queryset().filter(
            models.Q(folder='Trash') | 
            models.Q(folder='TRASH') |
            models.Q(folder='Deleted Items') |
            models.Q(folder__icontains='trash') |
            models.Q(folder__icontains='deleted') |
            models.Q(is_deleted=True)
        )


class SpamEmail(Email):
    """
    Proxy model for emails in the Spam/Junk folder.
    
    This model represents spam emails,
    allowing for specialized management of spam emails.
    """
    
    class Meta:
        proxy = True
        verbose_name = _('Spam Email')
        verbose_name_plural = _('Spam Emails')
        
    objects = EmailQuerySet.as_manager()
    
    def save(self, *args, **kwargs):
        """Override save to ensure folder is set correctly."""
        if not self.folder:
            self.folder = 'Spam'
        super().save(*args, **kwargs)
        
    @classmethod
    def get_queryset(cls):
        """Get queryset filtered to Spam emails only."""
        return super().get_queryset().filter(
            models.Q(folder='Spam') | 
            models.Q(folder='SPAM') |
            models.Q(folder='Junk') |
            models.Q(folder='JUNK') |
            models.Q(folder__icontains='spam') |
            models.Q(folder__icontains='junk')
        )


class ImportantEmail(Email):
    """
    Proxy model for important emails.
    
    This model represents emails marked as important,
    allowing for specialized management of important emails.
    """
    
    class Meta:
        proxy = True
        verbose_name = _('Important Email')
        verbose_name_plural = _('Important Emails')
        
    objects = EmailQuerySet.as_manager()
    
    @classmethod
    def get_queryset(cls):
        """Get queryset filtered to Important emails only."""
        return super().get_queryset().filter(
            models.Q(is_important=True) |
            models.Q(folder__icontains='important') |
            models.Q(flags__name__icontains='important')
        ).distinct()


class UnreadEmail(Email):
    """
    Proxy model for unread emails.
    
    This model represents emails that haven't been read,
    allowing for specialized management of unread emails.
    """
    
    class Meta:
        proxy = True
        verbose_name = _('Unread Email')
        verbose_name_plural = _('Unread Emails')
        
    objects = EmailQuerySet.as_manager()
    
    @classmethod
    def get_queryset(cls):
        """Get queryset filtered to Unread emails only."""
        return super().get_queryset().filter(is_read=False)


class FlaggedEmail(Email):
    """
    Proxy model for flagged emails.
    
    This model represents emails that have been flagged,
    allowing for specialized management of flagged emails.
    """
    
    class Meta:
        proxy = True
        verbose_name = _('Flagged Email')
        verbose_name_plural = _('Flagged Emails')
        
    objects = EmailQuerySet.as_manager()
    
    @classmethod
    def get_queryset(cls):
        """Get queryset filtered to Flagged emails only."""
        return super().get_queryset().filter(
            models.Q(is_flagged=True) |
            models.Q(flags__isnull=False)
        ).distinct()


class AttachmentEmail(Email):
    """
    Proxy model for emails with attachments.
    
    This model represents emails that have attachments,
    allowing for specialized management of emails with attachments.
    """
    
    class Meta:
        proxy = True
        verbose_name = _('Email with Attachments')
        verbose_name_plural = _('Emails with Attachments')
        
    objects = EmailQuerySet.as_manager()
    
    @classmethod
    def get_queryset(cls):
        """Get queryset filtered to emails with attachments only."""
        return super().get_queryset().filter(
            models.Q(has_attachments=True) |
            models.Q(attachments__isnull=False)
        ).distinct()


class RecentEmail(Email):
    """
    Proxy model for recent emails.
    
    This model represents emails from the last 30 days,
    allowing for specialized management of recent emails.
    """
    
    class Meta:
        proxy = True
        verbose_name = _('Recent Email')
        verbose_name_plural = _('Recent Emails')
        
    objects = EmailQuerySet.as_manager()
    
    @classmethod
    def get_queryset(cls):
        """Get queryset filtered to recent emails only."""
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        return super().get_queryset().filter(
            date_received__gte=thirty_days_ago
        )


class LargeEmail(Email):
    """
    Proxy model for large emails.
    
    This model represents emails larger than 1MB,
    allowing for specialized management of large emails.
    """
    
    class Meta:
        proxy = True
        verbose_name = _('Large Email')
        verbose_name_plural = _('Large Emails')
        
    objects = EmailQuerySet.as_manager()
    
    @classmethod
    def get_queryset(cls):
        """Get queryset filtered to large emails only."""
        return super().get_queryset().filter(
            size__gt=1024 * 1024  # 1MB
        )


# Mailbox proxy models for different folder types

class InboxMailbox(Mailbox):
    """
    Proxy model for INBOX mailboxes.
    
    This model represents INBOX mailboxes specifically.
    """
    
    class Meta:
        proxy = True
        verbose_name = _('Inbox Mailbox')
        verbose_name_plural = _('Inbox Mailboxes')
        
    def save(self, *args, **kwargs):
        """Override save to ensure name is set correctly."""
        if not self.name:
            self.name = 'INBOX'
        super().save(*args, **kwargs)
        
    @classmethod
    def get_queryset(cls):
        """Get queryset filtered to INBOX mailboxes only."""
        return super().get_queryset().filter(
            models.Q(name='INBOX') | 
            models.Q(name__iexact='inbox')
        )


class SentMailbox(Mailbox):
    """
    Proxy model for Sent mailboxes.
    
    This model represents Sent mailboxes specifically.
    """
    
    class Meta:
        proxy = True
        verbose_name = _('Sent Mailbox')
        verbose_name_plural = _('Sent Mailboxes')
        
    def save(self, *args, **kwargs):
        """Override save to ensure name is set correctly."""
        if not self.name:
            self.name = 'Sent'
        super().save(*args, **kwargs)
        
    @classmethod
    def get_queryset(cls):
        """Get queryset filtered to Sent mailboxes only."""
        return super().get_queryset().filter(
            models.Q(name='Sent') | 
            models.Q(name='SENT') |
            models.Q(name__icontains='sent')
        )


class DraftMailbox(Mailbox):
    """
    Proxy model for Draft mailboxes.
    
    This model represents Draft mailboxes specifically.
    """
    
    class Meta:
        proxy = True
        verbose_name = _('Draft Mailbox')
        verbose_name_plural = _('Draft Mailboxes')
        
    def save(self, *args, **kwargs):
        """Override save to ensure name is set correctly."""
        if not self.name:
            self.name = 'Drafts'
        super().save(*args, **kwargs)
        
    @classmethod
    def get_queryset(cls):
        """Get queryset filtered to Draft mailboxes only."""
        return super().get_queryset().filter(
            models.Q(name='Drafts') | 
            models.Q(name='DRAFTS') |
            models.Q(name__icontains='draft')
        )


class TrashMailbox(Mailbox):
    """
    Proxy model for Trash mailboxes.
    
    This model represents Trash mailboxes specifically.
    """
    
    class Meta:
        proxy = True
        verbose_name = _('Trash Mailbox')
        verbose_name_plural = _('Trash Mailboxes')
        
    def save(self, *args, **kwargs):
        """Override save to ensure name is set correctly."""
        if not self.name:
            self.name = 'Trash'
        super().save(*args, **kwargs)
        
    @classmethod
    def get_queryset(cls):
        """Get queryset filtered to Trash mailboxes only."""
        return super().get_queryset().filter(
            models.Q(name='Trash') | 
            models.Q(name='TRASH') |
            models.Q(name='Deleted Items') |
            models.Q(name__icontains='trash') |
            models.Q(name__icontains='deleted')
        )


class SpamMailbox(Mailbox):
    """
    Proxy model for Spam mailboxes.
    
    This model represents Spam mailboxes specifically.
    """
    
    class Meta:
        proxy = True
        verbose_name = _('Spam Mailbox')
        verbose_name_plural = _('Spam Mailboxes')
        
    def save(self, *args, **kwargs):
        """Override save to ensure name is set correctly."""
        if not self.name:
            self.name = 'Spam'
        super().save(*args, **kwargs)
        
    @classmethod
    def get_queryset(cls):
        """Get queryset filtered to Spam mailboxes only."""
        return super().get_queryset().filter(
            models.Q(name='Spam') | 
            models.Q(name='SPAM') |
            models.Q(name='Junk') |
            models.Q(name='JUNK') |
            models.Q(name__icontains='spam') |
            models.Q(name__icontains='junk')
        )


class CustomFolderMailbox(Mailbox):
    """
    Proxy model for custom folder mailboxes.
    
    This model represents custom folder mailboxes (not standard folders).
    """
    
    class Meta:
        proxy = True
        verbose_name = _('Custom Folder Mailbox')
        verbose_name_plural = _('Custom Folder Mailboxes')
        
    @classmethod
    def get_queryset(cls):
        """Get queryset filtered to custom folder mailboxes only."""
        standard_folders = [
            'INBOX', 'Sent', 'Drafts', 'Trash', 'Spam', 'Junk',
            'SENT', 'DRAFTS', 'TRASH', 'SPAM', 'JUNK',
            'Sent Items', 'Deleted Items'
        ]
        
        query = models.Q()
        for folder in standard_folders:
            query |= models.Q(name=folder)
            query |= models.Q(name__iexact=folder)
            query |= models.Q(name__icontains=folder.lower())
            
        return super().get_queryset().exclude(query)


# Utility functions for proxy models

def get_folder_type(folder_name: str) -> str:
    """
    Determine the folder type based on folder name.
    
    Args:
        folder_name: Name of the folder
        
    Returns:
        Folder type string
    """
    if not folder_name:
        return 'inbox'
        
    folder_lower = folder_name.lower()
    
    if folder_lower in ['inbox', 'inbox']:
        return 'inbox'
    elif 'sent' in folder_lower:
        return 'sent'
    elif 'draft' in folder_lower:
        return 'drafts'
    elif 'trash' in folder_lower or 'deleted' in folder_lower:
        return 'trash'
    elif 'spam' in folder_lower or 'junk' in folder_lower:
        return 'spam'
    else:
        return 'custom'


def get_proxy_model_for_folder(folder_name: str):
    """
    Get the appropriate proxy model class for a folder.
    
    Args:
        folder_name: Name of the folder
        
    Returns:
        Proxy model class
    """
    folder_type = get_folder_type(folder_name)
    
    proxy_models = {
        'inbox': InboxEmail,
        'sent': SentEmail,
        'drafts': DraftEmail,
        'trash': TrashEmail,
        'spam': SpamEmail,
        'custom': Email,  # Use base model for custom folders
    }
    
    return proxy_models.get(folder_type, Email)


def get_mailbox_proxy_model_for_folder(folder_name: str):
    """
    Get the appropriate mailbox proxy model class for a folder.
    
    Args:
        folder_name: Name of the folder
        
    Returns:
        Mailbox proxy model class
    """
    folder_type = get_folder_type(folder_name)
    
    proxy_models = {
        'inbox': InboxMailbox,
        'sent': SentMailbox,
        'drafts': DraftMailbox,
        'trash': TrashMailbox,
        'spam': SpamMailbox,
        'custom': CustomFolderMailbox,
    }
    
    return proxy_models.get(folder_type, Mailbox)


def get_folder_statistics(folder_name: str) -> dict:
    """
    Get statistics for a specific folder.
    
    Args:
        folder_name: Name of the folder
        
    Returns:
        Dictionary with folder statistics
    """
    proxy_model = get_proxy_model_for_folder(folder_name)
    queryset = proxy_model.get_queryset()
    
    return {
        'total_emails': queryset.count(),
        'unread_emails': queryset.filter(is_read=False).count(),
        'flagged_emails': queryset.filter(is_flagged=True).count(),
        'emails_with_attachments': queryset.filter(has_attachments=True).count(),
        'folder_type': get_folder_type(folder_name),
    }


def get_all_folder_statistics() -> dict:
    """
    Get statistics for all folder types.
    
    Returns:
        Dictionary with statistics for all folders
    """
    return {
        'inbox': get_folder_statistics('INBOX'),
        'sent': get_folder_statistics('Sent'),
        'drafts': get_folder_statistics('Drafts'),
        'trash': get_folder_statistics('Trash'),
        'spam': get_folder_statistics('Spam'),
    } 