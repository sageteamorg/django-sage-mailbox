"""
QuerySet classes for sage_mailbox repository layer.

This module provides custom QuerySet classes with domain-specific
query methods for email and mailbox operations.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from django.db import models
from django.db.models import Q, Count, Sum, Avg, Max, Min
from django.utils import timezone

from sage_imap.helpers.enums import Flag, DefaultMailboxes


class MailboxQuerySet(models.QuerySet):
    """Custom QuerySet for Mailbox model."""
    
    def active(self):
        """Filter mailboxes with active servers."""
        return self.filter(server__is_active=True)
    
    def for_server(self, server):
        """Filter mailboxes for a specific server."""
        return self.filter(server=server)
    
    def for_user(self, user):
        """Filter mailboxes for a specific user."""
        return self.filter(server__owner=user)
    
    def default_mailboxes(self):
        """Filter default system mailboxes."""
        return self.filter(is_default=True)
    
    def custom_mailboxes(self):
        """Filter custom user mailboxes."""
        return self.filter(is_default=False)
    
    def with_name(self, name):
        """Filter mailboxes by name."""
        return self.filter(name=name)
    
    def inbox(self):
        """Get INBOX mailboxes."""
        return self.filter(name=DefaultMailboxes.INBOX)
    
    def sent(self):
        """Get Sent mailboxes."""
        return self.filter(name=DefaultMailboxes.SENT)
    
    def drafts(self):
        """Get Drafts mailboxes."""
        return self.filter(name=DefaultMailboxes.DRAFTS)
    
    def trash(self):
        """Get Trash mailboxes."""
        return self.filter(name=DefaultMailboxes.TRASH)
    
    def spam(self):
        """Get Spam mailboxes."""
        return self.filter(name=DefaultMailboxes.SPAM)
    
    def archive(self):
        """Get Archive mailboxes."""
        return self.filter(name=DefaultMailboxes.ARCHIVE)
    
    def with_unseen_count(self):
        """Annotate with unseen email count."""
        return self.annotate(
            unseen_emails=Count(
                'emails',
                filter=Q(emails__is_seen=False, emails__is_deleted=False)
            )
        )
    
    def with_total_count(self):
        """Annotate with total email count."""
        return self.annotate(
            total_emails=Count('emails', filter=Q(emails__is_deleted=False))
        )
    
    def with_email_stats(self):
        """Annotate with comprehensive email statistics."""
        return self.annotate(
            total_emails=Count('emails', filter=Q(emails__is_deleted=False)),
            unseen_emails=Count(
                'emails',
                filter=Q(emails__is_seen=False, emails__is_deleted=False)
            ),
            flagged_emails=Count(
                'emails',
                filter=Q(emails__is_flagged=True, emails__is_deleted=False)
            ),
            latest_email=Max('emails__date'),
            oldest_email=Min('emails__date'),
            total_size=Sum('emails__size'),
            avg_size=Avg('emails__size'),
        )
    
    def needs_sync(self, hours=24):
        """Filter mailboxes that need synchronization."""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.filter(
            Q(last_sync__isnull=True) | Q(last_sync__lt=cutoff_time)
        )
    
    def recently_synced(self, hours=1):
        """Filter mailboxes that were recently synchronized."""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.filter(last_sync__gte=cutoff_time)


class EmailQuerySet(models.QuerySet):
    """Custom QuerySet for Email model."""
    
    def active(self):
        """Filter active emails (not deleted)."""
        return self.filter(is_deleted=False)
    
    def deleted(self):
        """Filter deleted emails."""
        return self.filter(is_deleted=True)
    
    def in_trash(self):
        """Filter emails in trash."""
        return self.filter(is_in_trash=True)
    
    def not_in_trash(self):
        """Filter emails not in trash."""
        return self.filter(is_in_trash=False)
    
    def seen(self):
        """Filter seen emails."""
        return self.filter(is_seen=True)
    
    def unseen(self):
        """Filter unseen emails."""
        return self.filter(is_seen=False)
    
    def flagged(self):
        """Filter flagged emails."""
        return self.filter(is_flagged=True)
    
    def unflagged(self):
        """Filter unflagged emails."""
        return self.filter(is_flagged=False)
    
    def answered(self):
        """Filter answered emails."""
        return self.filter(is_answered=True)
    
    def unanswered(self):
        """Filter unanswered emails."""
        return self.filter(is_answered=False)
    
    def drafts(self):
        """Filter draft emails."""
        return self.filter(is_draft=True)
    
    def recent(self):
        """Filter recent emails."""
        return self.filter(is_recent=True)
    
    def for_mailbox(self, mailbox):
        """Filter emails for a specific mailbox."""
        return self.filter(mailbox=mailbox)
    
    def for_server(self, server):
        """Filter emails for a specific server."""
        return self.filter(mailbox__server=server)
    
    def for_user(self, user):
        """Filter emails for a specific user."""
        return self.filter(mailbox__server__owner=user)
    
    def from_address(self, address):
        """Filter emails from a specific address."""
        return self.filter(from_address__icontains=address)
    
    def to_address(self, address):
        """Filter emails to a specific address."""
        return self.filter(to_addresses__icontains=address)
    
    def with_subject(self, subject):
        """Filter emails with subject containing text."""
        return self.filter(subject__icontains=subject)
    
    def with_body(self, text):
        """Filter emails with body containing text."""
        return self.filter(
            Q(plain_body__icontains=text) | Q(html_body__icontains=text)
        )
    
    def with_attachments(self):
        """Filter emails with attachments."""
        return self.filter(attachments__isnull=False).distinct()
    
    def without_attachments(self):
        """Filter emails without attachments."""
        return self.filter(attachments__isnull=True)
    
    def date_range(self, start_date, end_date):
        """Filter emails within a date range."""
        return self.filter(date__range=[start_date, end_date])
    
    def today(self):
        """Filter emails from today."""
        today = timezone.now().date()
        return self.filter(date__date=today)
    
    def yesterday(self):
        """Filter emails from yesterday."""
        yesterday = timezone.now().date() - timedelta(days=1)
        return self.filter(date__date=yesterday)
    
    def this_week(self):
        """Filter emails from this week."""
        today = timezone.now().date()
        start_week = today - timedelta(days=today.weekday())
        return self.filter(date__date__gte=start_week)
    
    def this_month(self):
        """Filter emails from this month."""
        today = timezone.now().date()
        start_month = today.replace(day=1)
        return self.filter(date__date__gte=start_month)
    
    def last_days(self, days=7):
        """Filter emails from the last N days."""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(date__gte=cutoff_date)
    
    def size_range(self, min_size=None, max_size=None):
        """Filter emails by size range."""
        queryset = self
        if min_size is not None:
            queryset = queryset.filter(size__gte=min_size)
        if max_size is not None:
            queryset = queryset.filter(size__lte=max_size)
        return queryset
    
    def large_emails(self, size_mb=10):
        """Filter large emails (default > 10MB)."""
        size_bytes = size_mb * 1024 * 1024
        return self.filter(size__gt=size_bytes)
    
    def with_uids(self, uids):
        """Filter emails by UIDs."""
        return self.filter(uid__in=uids)
    
    def with_message_ids(self, message_ids):
        """Filter emails by Message IDs."""
        return self.filter(message_id__in=message_ids)
    
    def inbox_emails(self):
        """Filter emails in INBOX."""
        return self.filter(mailbox__name=DefaultMailboxes.INBOX)
    
    def sent_emails(self):
        """Filter emails in Sent folder."""
        return self.filter(mailbox__name=DefaultMailboxes.SENT)
    
    def draft_emails(self):
        """Filter emails in Drafts folder."""
        return self.filter(mailbox__name=DefaultMailboxes.DRAFTS)
    
    def trash_emails(self):
        """Filter emails in Trash folder."""
        return self.filter(mailbox__name=DefaultMailboxes.TRASH)
    
    def spam_emails(self):
        """Filter emails in Spam folder."""
        return self.filter(mailbox__name=DefaultMailboxes.SPAM)
    
    def archive_emails(self):
        """Filter emails in Archive folder."""
        return self.filter(mailbox__name=DefaultMailboxes.ARCHIVE)
    
    def search(self, query):
        """Full-text search across email content."""
        return self.filter(
            Q(subject__icontains=query) |
            Q(plain_body__icontains=query) |
            Q(html_body__icontains=query) |
            Q(from_address__icontains=query) |
            Q(to_addresses__icontains=query)
        )
    
    def with_flag(self, flag):
        """Filter emails with a specific flag."""
        flag_filters = {
            Flag.SEEN: Q(is_seen=True),
            Flag.ANSWERED: Q(is_answered=True),
            Flag.FLAGGED: Q(is_flagged=True),
            Flag.DELETED: Q(is_deleted=True),
            Flag.DRAFT: Q(is_draft=True),
            Flag.RECENT: Q(is_recent=True),
        }
        return self.filter(flag_filters.get(flag, Q()))
    
    def without_flag(self, flag):
        """Filter emails without a specific flag."""
        flag_filters = {
            Flag.SEEN: Q(is_seen=False),
            Flag.ANSWERED: Q(is_answered=False),
            Flag.FLAGGED: Q(is_flagged=False),
            Flag.DELETED: Q(is_deleted=False),
            Flag.DRAFT: Q(is_draft=False),
            Flag.RECENT: Q(is_recent=False),
        }
        return self.filter(flag_filters.get(flag, Q()))
    
    def by_priority(self, reverse=False):
        """Order emails by priority (flagged first, then by date)."""
        order_fields = ['-is_flagged', '-date']
        if reverse:
            order_fields = ['is_flagged', 'date']
        return self.order_by(*order_fields)
    
    def by_date(self, reverse=False):
        """Order emails by date."""
        order_field = '-date' if not reverse else 'date'
        return self.order_by(order_field)
    
    def by_size(self, reverse=False):
        """Order emails by size."""
        order_field = '-size' if not reverse else 'size'
        return self.order_by(order_field)
    
    def by_subject(self, reverse=False):
        """Order emails by subject."""
        order_field = '-subject' if reverse else 'subject'
        return self.order_by(order_field)
    
    def by_sender(self, reverse=False):
        """Order emails by sender."""
        order_field = '-from_address' if reverse else 'from_address'
        return self.order_by(order_field)
    
    def with_statistics(self):
        """Annotate with email statistics."""
        return self.annotate(
            attachment_count=Count('attachments'),
            total_attachment_size=Sum('attachments__size'),
        )
    
    def duplicate_message_ids(self):
        """Find emails with duplicate message IDs."""
        return self.values('message_id').annotate(
            count=Count('message_id')
        ).filter(count__gt=1)
    
    def orphaned_emails(self):
        """Find emails with non-existent mailboxes."""
        return self.filter(mailbox__isnull=True)
    
    def bulk_flag_update(self, flag, value=True):
        """Bulk update flag for queryset."""
        flag_fields = {
            Flag.SEEN: 'is_seen',
            Flag.ANSWERED: 'is_answered',
            Flag.FLAGGED: 'is_flagged',
            Flag.DELETED: 'is_deleted',
            Flag.DRAFT: 'is_draft',
            Flag.RECENT: 'is_recent',
        }
        
        field_name = flag_fields.get(flag)
        if field_name:
            return self.update(**{field_name: value})
        return 0
    
    def bulk_move_to_trash(self):
        """Bulk move emails to trash."""
        return self.update(
            is_in_trash=True,
            deleted_at=timezone.now(),
            original_mailbox=models.F('mailbox')
        )
    
    def bulk_restore_from_trash(self):
        """Bulk restore emails from trash."""
        return self.update(
            is_in_trash=False,
            deleted_at=None,
            mailbox=models.F('original_mailbox'),
            original_mailbox=None
        )
    
    def bulk_permanent_delete(self):
        """Bulk permanently delete emails."""
        return self.delete()
    
    def get_by_uid(self, uid, mailbox=None):
        """Get email by UID and optional mailbox."""
        queryset = self.filter(uid=uid)
        if mailbox:
            queryset = queryset.filter(mailbox=mailbox)
        return queryset.first()
    
    def get_by_message_id(self, message_id):
        """Get email by Message ID."""
        return self.filter(message_id=message_id).first()
    
    def get_thread_emails(self, message_id):
        """Get emails in the same thread (same message ID or references)."""
        # This is a simplified implementation
        # In a real implementation, you'd parse References and In-Reply-To headers
        return self.filter(
            Q(message_id=message_id) |
            Q(headers__contains=message_id)
        )
    
    def export_data(self, fields=None):
        """Export email data for backup or migration."""
        if fields is None:
            fields = [
                'uid', 'message_id', 'subject', 'from_address',
                'to_addresses', 'date', 'size', 'is_seen',
                'is_flagged', 'is_answered'
            ]
        return self.values(*fields) 