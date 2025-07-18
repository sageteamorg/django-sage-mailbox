"""
Django admin configuration for email models.

This module provides admin interfaces for managing emails
with composition, reply, forward capabilities and flag management.
"""

import json
import logging
from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.utils import unquote
from django.db.models import Count
from django.forms import ModelForm, Textarea
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _

from ..models import Email
# Proxy models removed as requested
from ..forms import EmailForm, EmailComposeForm
from ..utils import format_file_size
from .base import BaseModelAdmin

logger = logging.getLogger(__name__)


class HasAttachmentFilter(admin.SimpleListFilter):
    """Filter emails by whether they have attachments."""
    
    title = _('Has Attachments')
    parameter_name = 'has_attachments'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', _('Yes')),
            ('no', _('No')),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(attachments__isnull=False).distinct()
        elif self.value() == 'no':
            return queryset.filter(attachments__isnull=True)
        return queryset


class BaseEmailAdmin(BaseModelAdmin):
    """Base admin class for all email proxy models."""
    
    list_display = [
        'subject_truncated', 'from_address', 'mailbox', 'date',
        'size_formatted', 'flag_indicators', 'attachment_count',
        'send_status', 'priority', 'is_outgoing'
    ]
    list_display_links = ['subject_truncated']
    list_filter = [
        'mailbox', 'is_seen', 'is_flagged', 'is_answered', 'is_deleted',
        'is_in_trash', 'date', 'mailbox__server', 'send_status', 'priority',
        'is_outgoing', 'smtp_server', HasAttachmentFilter
    ]
    search_fields = [
        'subject', 'from_address', 'message_id', 'plain_body',
        'to_addresses', 'cc_addresses'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'uid', 'size', 'headers_formatted',
        'raw_content_preview', 'message_id', 'sent_at', 'send_attempts'
    ]
    date_hierarchy = 'date'
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('mailbox', 'uid', 'message_id', 'subject', 'date')
        }),
        (_('Addresses'), {
            'fields': ('from_address', 'from_name', 'to_addresses', 'cc_addresses', 'bcc_addresses', 'reply_to')
        }),
        (_('Content'), {
            'fields': ('plain_body', 'html_body', 'size'),
            'classes': ('collapse',)
        }),
        (_('Composition & Sending'), {
            'fields': ('smtp_server', 'template', 'priority', 'is_outgoing', 'send_status', 'sent_at', 'send_attempts', 'send_error'),
            'classes': ('collapse',)
        }),
        (_('Email Threading'), {
            'fields': ('in_reply_to', 'references'),
            'classes': ('collapse',)
        }),
        (_('Flags'), {
            'fields': ('is_seen', 'is_answered', 'is_flagged', 'is_deleted', 'is_draft', 'is_recent')
        }),
        (_('Trash Management'), {
            'fields': ('is_in_trash', 'original_mailbox', 'deleted_at'),
            'classes': ('collapse',)
        }),
        (_('Headers'), {
            'fields': ('headers_formatted',),
            'classes': ('collapse',)
        }),
        (_('Raw Content'), {
            'fields': ('raw_content_preview',),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Add optimizations to queryset."""
        return super().get_queryset(request).select_related('mailbox', 'mailbox__server').annotate(
            attachment_count=Count('attachments')
        )
    
    def subject_truncated(self, obj):
        """Display truncated subject."""
        return Truncator(obj.subject).chars(60)
    subject_truncated.short_description = _('Subject')
    subject_truncated.admin_order_field = 'subject'
    
    def size_formatted(self, obj):
        """Display formatted file size."""
        return format_file_size(obj.size)
    size_formatted.short_description = _('Size')
    size_formatted.admin_order_field = 'size'
    
    def flag_indicators(self, obj):
        """Display flag indicators."""
        flags = []
        if obj.is_seen:
            flags.append('<span class="flag-seen" title="Seen">👁</span>')
        if obj.is_flagged:
            flags.append('<span class="flag-flagged" title="Flagged">🚩</span>')
        if obj.is_answered:
            flags.append('<span class="flag-answered" title="Answered">↩</span>')
        if obj.is_deleted:
            flags.append('<span class="flag-deleted" title="Deleted">🗑</span>')
        if obj.is_draft:
            flags.append('<span class="flag-draft" title="Draft">📝</span>')
        if obj.is_in_trash:
            flags.append('<span class="flag-trash" title="In Trash">🗑</span>')
        
        return format_html(' '.join(flags))
    flag_indicators.short_description = _('Flags')
    
    def attachment_count(self, obj):
        """Display attachment count."""
        count = obj.attachment_count
        if count > 0:
            return format_html('<span title="Attachments">📎 {}</span>', count)
        return '-'
    attachment_count.short_description = _('Attachments')
    attachment_count.admin_order_field = 'attachment_count'
    
    def headers_formatted(self, obj):
        """Display formatted headers."""
        if obj.headers:
            formatted_headers = json.dumps(obj.headers, indent=2)
            return format_html('<pre>{}</pre>', formatted_headers)
        return '-'
    headers_formatted.short_description = _('Headers')
    
    def raw_content_preview(self, obj):
        """Display raw content preview."""
        if obj.raw_content:
            preview = obj.raw_content[:1000].decode('utf-8', errors='ignore')
            return format_html('<pre>{}</pre>', preview)
        return '-'
    raw_content_preview.short_description = _('Raw Content Preview')


@admin.register(Email)
class EmailAdmin(BaseEmailAdmin):
    """Admin interface for Email model with sage_imap integration."""
    
    form = EmailForm
    autocomplete_fields = ['mailbox', 'smtp_server', 'template', 'original_mailbox']
    
    actions = [
        'mark_as_read_sage_imap', 'mark_as_unread_sage_imap', 
        'mark_as_flagged_sage_imap', 'mark_as_unflagged_sage_imap',
        'move_to_trash_sage_imap', 'restore_from_trash_sage_imap', 
        'permanent_delete_sage_imap', 'download_as_eml_sage_imap',
        'sync_flags_sage_imap', 'get_email_flags'
    ]

    def get_urls(self):
        """Add custom URLs for email composition."""
        urls = super().get_urls()
        custom_urls = [
            path('compose/', self.admin_site.admin_view(self.compose_email_view), name='sage_mailbox_email_compose'),
            path('<path:object_id>/reply/', self.admin_site.admin_view(self.reply_email_view), name='sage_mailbox_email_reply'),
            path('<path:object_id>/forward/', self.admin_site.admin_view(self.forward_email_view), name='sage_mailbox_email_forward'),
        ]
        return custom_urls + urls

    def has_add_permission(self, request):
        """Disable regular add functionality - emails should only be composed or synced."""
        return False

    def changelist_view(self, request, extra_context=None):
        """Add compose button to changelist view."""
        extra_context = extra_context or {}
        extra_context['compose_url'] = reverse('admin:sage_mailbox_email_compose')
        return super().changelist_view(request, extra_context)

    def compose_email_view(self, request):
        """Compose and send new email."""
        if request.method == 'POST':
            form = EmailComposeForm(request.user, request.POST)
            if form.is_valid():
                return self._handle_email_composition_form(request, 'compose', form)
        else:
            form = EmailComposeForm(request.user)
        
        # Show composition form
        return render(request, 'admin/sage_mailbox/compose_email.html', {
            'title': 'Compose New Email',
            'action': 'compose',
            'form': form,
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
        })

    def reply_email_view(self, request, object_id):
        """Reply to selected email."""
        email = get_object_or_404(Email, pk=unquote(object_id))
        
        if request.method == 'POST':
            form = EmailComposeForm(request.user, request.POST)
            if form.is_valid():
                return self._handle_email_composition_form(request, 'reply', form, email)
        else:
            # Pre-populate form for reply
            initial_data = {
                'to_addresses': email.from_address,
                'subject': f'Re: {email.subject}',
            }
            form = EmailComposeForm(request.user, initial=initial_data)
        
        # Show reply form
        return render(request, 'admin/sage_mailbox/compose_email.html', {
            'title': f'Reply to: {email.subject}',
            'action': 'reply',
            'original_email': email,
            'form': form,
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
        })

    def forward_email_view(self, request, object_id):
        """Forward selected email."""
        email = get_object_or_404(Email, pk=unquote(object_id))
        
        if request.method == 'POST':
            form = EmailComposeForm(request.user, request.POST)
            if form.is_valid():
                return self._handle_email_composition_form(request, 'forward', form, email)
        else:
            # Pre-populate form for forward
            initial_data = {
                'subject': f'Fwd: {email.subject}',
                'body_html': email.html_body or '',
                'body_plain': email.plain_body or '',
            }
            form = EmailComposeForm(request.user, initial=initial_data)
        
        # Show forward form
        return render(request, 'admin/sage_mailbox/compose_email.html', {
            'title': f'Forward: {email.subject}',
            'action': 'forward',
            'original_email': email,
            'form': form,
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
        })
    
    def mark_as_read_sage_imap(self, request, queryset):
        """Mark selected emails as read using repository method."""
        try:
            updated = Email.objects.mark_as_read(queryset)
            messages.success(request, f"✓ Marked {updated} email(s) as read")
        except Exception as e:
            messages.error(request, f"✗ Failed to mark emails as read: {e}")
    
    mark_as_read_sage_imap.short_description = _('Mark as read (repository)')
    
    def mark_as_unread_sage_imap(self, request, queryset):
        """Mark selected emails as unread using repository method."""
        try:
            updated = Email.objects.mark_as_unread(queryset)
            messages.success(request, f"✓ Marked {updated} email(s) as unread")
        except Exception as e:
            messages.error(request, f"✗ Failed to mark emails as unread: {e}")
    
    mark_as_unread_sage_imap.short_description = _('Mark as unread (repository)')
    
    def mark_as_flagged_sage_imap(self, request, queryset):
        """Mark selected emails as flagged using repository method."""
        try:
            updated = Email.objects.mark_as_flagged(queryset)
            messages.success(request, f"✓ Marked {updated} email(s) as flagged")
        except Exception as e:
            messages.error(request, f"✗ Failed to mark emails as flagged: {e}")
    
    mark_as_flagged_sage_imap.short_description = _('Mark as flagged (repository)')
    
    def mark_as_unflagged_sage_imap(self, request, queryset):
        """Mark selected emails as unflagged using repository method."""
        try:
            updated = Email.objects.mark_as_unflagged(queryset)
            messages.success(request, f"✓ Marked {updated} email(s) as unflagged")
        except Exception as e:
            messages.error(request, f"✗ Failed to mark emails as unflagged: {e}")
    
    mark_as_unflagged_sage_imap.short_description = _('Mark as unflagged (repository)')
    
    def move_to_trash_sage_imap(self, request, queryset):
        """Move selected emails to trash using repository method."""
        try:
            updated = Email.objects.move_to_trash(queryset)
            messages.success(request, f"✓ Moved {updated} email(s) to trash")
        except Exception as e:
            messages.error(request, f"✗ Failed to move emails to trash: {e}")
    
    move_to_trash_sage_imap.short_description = _('Move to trash (repository)')
    
    def restore_from_trash_sage_imap(self, request, queryset):
        """Restore selected emails from trash using repository method."""
        try:
            updated = Email.objects.restore_from_trash(queryset)
            messages.success(request, f"✓ Restored {updated} email(s) from trash")
        except Exception as e:
            messages.error(request, f"✗ Failed to restore emails from trash: {e}")
    
    restore_from_trash_sage_imap.short_description = _('Restore from trash (repository)')
    
    def permanent_delete_sage_imap(self, request, queryset):
        """Permanently delete selected emails using repository method."""
        try:
            deleted = Email.objects.permanent_delete(queryset)
            messages.success(request, f"✓ Permanently deleted {deleted} email(s)")
        except Exception as e:
            messages.error(request, f"✗ Failed to permanently delete emails: {e}")
    
    permanent_delete_sage_imap.short_description = _('Permanently delete (repository)')
    
    def download_as_eml_sage_imap(self, request, queryset):
        """Download selected emails as EML files using repository method."""
        if queryset.count() == 1:
            email = queryset.first()
            try:
                eml_content = Email.objects.download_as_eml(email)
                response = HttpResponse(eml_content, content_type='message/rfc822')
                response['Content-Disposition'] = f'attachment; filename="{email.subject or "email"}.eml"'
                return response
            except Exception as e:
                messages.error(request, f"✗ Failed to download email: {e}")
        else:
            messages.error(request, "Please select only one email for EML download")
    
    download_as_eml_sage_imap.short_description = _('Download as EML (repository)')
    
    def sync_flags_sage_imap(self, request, queryset):
        """Sync flags for selected emails using repository method."""
        try:
            success_count = 0
            for email in queryset:
                try:
                    created, updated = Email.objects.sync_emails_from_server(
                        email.mailbox, full_sync=False, limit=1
                    )
                    success_count += 1
                except Exception as e:
                    logger.error(f"Flag sync failed for email {email.uid}: {e}")
                    continue
            
            messages.success(request, f"✓ Synced flags for {success_count} email(s)")
        except Exception as e:
            messages.error(request, f"✗ Failed to sync flags: {e}")
    
    sync_flags_sage_imap.short_description = _('Sync flags (repository)')
    
    def get_email_flags(self, request, queryset):
        """Get current flags for selected emails from database."""
        for email in queryset[:5]:  # Limit to first 5 emails
            flag_list = []
            if email.is_seen:
                flag_list.append('\\Seen')
            if email.is_flagged:
                flag_list.append('\\Flagged')
            if email.is_answered:
                flag_list.append('\\Answered')
            if email.is_deleted:
                flag_list.append('\\Deleted')
            if email.is_draft:
                flag_list.append('\\Draft')
            if email.is_recent:
                flag_list.append('\\Recent')
            
            messages.info(
                request,
                f"🏷 {email.subject[:50]}: {', '.join(flag_list) if flag_list else 'No flags'}"
            )
    
    get_email_flags.short_description = _('Get email flags (from database)')
    
    def _handle_email_composition_form(self, request, action, form, original_email=None):
        """Handle email composition form submission using Django form."""
        try:
            # Get cleaned form data
            smtp_server = form.cleaned_data['smtp_server']
            template = form.cleaned_data.get('template')
            to_addresses = form.cleaned_data['to_addresses']
            cc_addresses = form.cleaned_data['cc_addresses']
            bcc_addresses = form.cleaned_data['bcc_addresses']
            subject = form.cleaned_data['subject']
            body_html = form.cleaned_data['body_html']
            body_plain = form.cleaned_data['body_plain']
            priority = form.cleaned_data['priority']
            
            # Create email service
            from ..services.email_service import EmailSendingService
            service = EmailSendingService(smtp_server=smtp_server)
            
            # Handle different actions
            if action == 'compose':
                # Send new email with IMAP Sent folder save
                email = service.send_email(
                    to_addresses=to_addresses,
                    subject=subject,
                    body_html=body_html,
                    body_plain=body_plain,
                    cc_addresses=cc_addresses,
                    bcc_addresses=bcc_addresses,
                    priority=priority,
                    template=template,
                    save_to_sent=True  # Save to IMAP Sent folder
                )
                
                messages.success(request, f"✓ Email '{subject}' sent successfully to {len(to_addresses)} recipient(s) and saved to Sent folder")
                
            elif action == 'reply':
                # Create reply with IMAP Sent folder save
                reply_email = service.create_reply(
                    original_email=original_email,
                    reply_body_html=body_html,
                    reply_body_plain=body_plain
                )
                
                # Update recipients if changed
                if to_addresses:
                    reply_email.to_addresses = to_addresses
                if cc_addresses:
                    reply_email.cc_addresses = cc_addresses
                if bcc_addresses:
                    reply_email.bcc_addresses = bcc_addresses
                
                reply_email.priority = priority
                reply_email.save()
                
                # Send reply with IMAP Sent folder save
                service.send_email(
                    to_addresses=reply_email.to_addresses,
                    subject=reply_email.subject,
                    body_html=reply_email.html_body,
                    body_plain=reply_email.plain_body,
                    cc_addresses=reply_email.cc_addresses,
                    bcc_addresses=reply_email.bcc_addresses,
                    priority=reply_email.priority,
                    in_reply_to=reply_email.in_reply_to,
                    references=reply_email.references,
                    template=template,
                    save_to_sent=True  # Save to IMAP Sent folder
                )
                
                messages.success(request, f"✓ Reply sent successfully and saved to Sent folder")
                
            elif action == 'forward':
                # Create forward with IMAP Sent folder save
                forward_email = service.create_forward(
                    original_email=original_email,
                    forward_body_html=body_html,
                    forward_body_plain=body_plain
                )
                
                # Update recipients
                forward_email.to_addresses = to_addresses
                forward_email.cc_addresses = cc_addresses
                forward_email.bcc_addresses = bcc_addresses
                forward_email.priority = priority
                forward_email.save()
                
                # Send forward with IMAP Sent folder save
                service.send_email(
                    to_addresses=forward_email.to_addresses,
                    subject=forward_email.subject,
                    body_html=forward_email.html_body,
                    body_plain=forward_email.plain_body,
                    cc_addresses=forward_email.cc_addresses,
                    bcc_addresses=forward_email.bcc_addresses,
                    priority=forward_email.priority,
                    template=template,
                    save_to_sent=True  # Save to IMAP Sent folder
                )
                
                messages.success(request, f"✓ Email forwarded successfully and saved to Sent folder")
            
            return redirect('admin:sage_mailbox_email_changelist')
            
        except Exception as e:
            messages.error(request, f"Failed to send email: {str(e)}")
            return redirect('admin:sage_mailbox_email_changelist')


# Proxy admin classes removed as requested - use filters instead 