"""
Additional admin actions for sage_mailbox application.

This module provides extended admin actions for bulk operations,
file upload/download, and advanced email management features.
"""

import zipfile
from io import BytesIO
from typing import List, Tuple

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.core.files.uploadedfile import UploadedFile
from django.forms import FileField, Form, ModelForm
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Email, Mailbox, Attachment
from .utils import FileUtils, EmailUtils, format_file_size
from .validators import validate_filename

from sage_imap.models.email import EmailMessage as SageEmailMessage


class UploadEMLForm(Form):
    """Form for uploading EML files."""
    
    mailbox = admin.widgets.ForeignKeyRawIdWidget(
        rel=Mailbox._meta.get_field('server').remote_field,
        admin_site=admin.site
    )
    
    eml_files = FileField(
        label=_('EML Files'),
        help_text=_('Select .eml files or .zip archive containing .eml files'),
        widget=admin.widgets.AdminFileWidget(attrs={'multiple': True})
    )
    
    def clean_eml_files(self):
        """Validate uploaded files."""
        files = self.files.getlist('eml_files')
        
        if not files:
            raise ValidationError(_('No files selected'))
        
        for file in files:
            # Check file size
            if file.size > 25 * 1024 * 1024:  # 25MB limit
                raise ValidationError(
                    _('File %(name)s is too large (max 25MB)'),
                    params={'name': file.name}
                )
            
            # Check file extension
            if not (file.name.endswith('.eml') or file.name.endswith('.zip')):
                raise ValidationError(
                    _('File %(name)s is not a valid .eml or .zip file'),
                    params={'name': file.name}
                )
        
        return files


class CleanTrashForm(Form):
    """Form for cleaning trash."""
    
    days_old = admin.widgets.AdminIntegerFieldWidget(
        attrs={'min': 1, 'max': 365, 'value': 30}
    )
    
    confirm = admin.widgets.AdminBooleanFieldWidget(
        label=_('Confirm permanent deletion'),
        help_text=_('This action cannot be undone')
    )


def upload_eml_action(modeladmin, request, queryset):
    """Action to upload EML files to mailbox."""
    
    if 'apply' in request.POST:
        form = UploadEMLForm(request.POST, request.FILES)
        
        if form.is_valid():
            mailbox_id = form.cleaned_data['mailbox']
            mailbox = Mailbox.objects.get(id=mailbox_id)
            files = form.cleaned_data['eml_files']
            
            uploaded_count = 0
            errors = []
            
            for file in files:
                try:
                    if file.name.endswith('.zip'):
                        # Extract ZIP file
                        zip_files = FileUtils.extract_zip_file(file.read())
                        
                        for filename, content in zip_files:
                            if filename.endswith('.eml'):
                                try:
                                    email = Email.objects.upload_eml_file(mailbox, content)
                                    uploaded_count += 1
                                except Exception as e:
                                    errors.append(f"Failed to upload {filename}: {e}")
                    
                    elif file.name.endswith('.eml'):
                        # Single EML file
                        email = Email.objects.upload_eml_file(mailbox, file.read())
                        uploaded_count += 1
                
                except Exception as e:
                    errors.append(f"Failed to process {file.name}: {e}")
            
            if uploaded_count > 0:
                messages.success(
                    request,
                    f"Successfully uploaded {uploaded_count} email(s) to {mailbox.name}"
                )
            
            for error in errors:
                messages.error(request, error)
            
            return HttpResponseRedirect(request.get_full_path())
    
    else:
        form = UploadEMLForm()
    
    return render(
        request,
        'admin/sage_mailbox/upload_eml.html',
        {
            'form': form,
            'title': _('Upload EML Files'),
            'queryset': queryset,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
        }
    )


def download_multiple_eml_action(modeladmin, request, queryset):
    """Action to download multiple emails as ZIP."""
    
    if queryset.count() == 0:
        messages.error(request, _('No emails selected'))
        return
    
    if queryset.count() == 1:
        # Single email - download as EML
        email = queryset.first()
        try:
            eml_content = Email.objects.download_as_eml(email)
            response = HttpResponse(eml_content, content_type='message/rfc822')
            filename = f"{email.subject or 'email'}_{email.uid}.eml"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            messages.error(request, f"Failed to download email: {e}")
            return
    
    # Multiple emails - create ZIP
    files = []
    
    for email in queryset:
        try:
            eml_content = Email.objects.download_as_eml(email)
            filename = f"{email.subject or 'email'}_{email.uid}.eml"
            # Sanitize filename
            filename = FileUtils.sanitize_filename(filename)
            files.append((filename, eml_content))
        except Exception as e:
            messages.warning(request, f"Failed to include email {email.uid}: {e}")
    
    if not files:
        messages.error(request, _('No emails could be downloaded'))
        return
    
    # Create ZIP file
    zip_filename = f"emails_{len(files)}_items.zip"
    zip_content = FileUtils.create_zip_file(files, zip_filename)
    
    response = HttpResponse(zip_content, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
    
    return response


def clean_trash_action(modeladmin, request, queryset):
    """Action to clean trash by permanently deleting old emails."""
    
    if 'apply' in request.POST:
        form = CleanTrashForm(request.POST)
        
        if form.is_valid():
            days_old = form.cleaned_data['days_old']
            confirm = form.cleaned_data['confirm']
            
            if not confirm:
                messages.error(request, _('Please confirm permanent deletion'))
                return HttpResponseRedirect(request.get_full_path())
            
            deleted_count = 0
            
            for mailbox in queryset:
                try:
                    count = Email.objects.clean_trash(mailbox, days_old)
                    deleted_count += count
                except Exception as e:
                    messages.error(request, f"Failed to clean trash for {mailbox.name}: {e}")
            
            if deleted_count > 0:
                messages.success(
                    request,
                    f"Permanently deleted {deleted_count} email(s) from trash"
                )
            else:
                messages.info(request, _('No emails found in trash older than specified days'))
            
            return HttpResponseRedirect(request.get_full_path())
    
    else:
        form = CleanTrashForm()
    
    # Calculate trash statistics
    trash_stats = []
    for mailbox in queryset:
        trash_count = Email.objects.filter(
            mailbox=mailbox,
            is_in_trash=True
        ).count()
        trash_stats.append({
            'mailbox': mailbox,
            'count': trash_count
        })
    
    return render(
        request,
        'admin/sage_mailbox/clean_trash.html',
        {
            'form': form,
            'title': _('Clean Trash'),
            'queryset': queryset,
            'trash_stats': trash_stats,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
        }
    )


def bulk_flag_action(flag_type, flag_value):
    """Generate bulk flag action."""
    
    def action(modeladmin, request, queryset):
        operation_map = {
            ('seen', True): 'mark_read',
            ('seen', False): 'mark_unread',
            ('flagged', True): 'mark_flagged',
            ('flagged', False): 'mark_unflagged',
            ('trash', True): 'move_to_trash',
            ('trash', False): 'restore_from_trash',
        }
        
        operation = operation_map.get((flag_type, flag_value))
        
        if operation:
            try:
                result = Email.objects.bulk_operations(queryset, operation)
                
                action_names = {
                    'mark_read': 'marked as read',
                    'mark_unread': 'marked as unread',
                    'mark_flagged': 'marked as flagged',
                    'mark_unflagged': 'marked as unflagged',
                    'move_to_trash': 'moved to trash',
                    'restore_from_trash': 'restored from trash',
                }
                
                messages.success(
                    request,
                    f"Successfully {action_names[operation]} {result} email(s)"
                )
                
            except Exception as e:
                messages.error(request, f"Bulk operation failed: {e}")
        else:
            messages.error(request, "Invalid flag operation")
    
    return action


def sync_emails_action(modeladmin, request, queryset):
    """Action to sync emails for selected mailboxes."""
    
    total_created = 0
    total_updated = 0
    
    for mailbox in queryset:
        try:
            created, updated = Email.objects.sync_emails_from_server(
                mailbox, full_sync=False, limit=100
            )
            total_created += created
            total_updated += updated
        except Exception as e:
            messages.error(request, f"Sync failed for {mailbox.name}: {e}")
    
    if total_created > 0 or total_updated > 0:
        messages.success(
            request,
            f"Sync completed: {total_created} created, {total_updated} updated"
        )
    else:
        messages.info(request, "No new emails found")


def full_sync_emails_action(modeladmin, request, queryset):
    """Action to perform full sync for selected mailboxes."""
    
    total_created = 0
    total_updated = 0
    
    for mailbox in queryset:
        try:
            created, updated = Email.objects.sync_emails_from_server(
                mailbox, full_sync=True, limit=1000
            )
            total_created += created
            total_updated += updated
        except Exception as e:
            messages.error(request, f"Full sync failed for {mailbox.name}: {e}")
    
    if total_created > 0 or total_updated > 0:
        messages.success(
            request,
            f"Full sync completed: {total_created} created, {total_updated} updated"
        )
    else:
        messages.info(request, "No emails to sync")


def export_email_data_action(modeladmin, request, queryset):
    """Action to export email data as CSV."""
    
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="emails_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'UID', 'Subject', 'From', 'To', 'Date', 'Size', 'Mailbox',
        'Is Seen', 'Is Flagged', 'Is Answered', 'Attachment Count'
    ])
    
    for email in queryset:
        writer.writerow([
            email.uid,
            email.subject,
            email.from_address,
            ', '.join(email.to_addresses) if email.to_addresses else '',
            email.date,
            email.size,
            email.mailbox.name,
            email.is_seen,
            email.is_flagged,
            email.is_answered,
            email.attachments.count()
        ])
    
    return response


def get_email_statistics_action(modeladmin, request, queryset):
    """Action to display email statistics."""
    
    stats = Email.objects.get_statistics()
    
    messages.info(
        request,
        f"Statistics - Total: {stats['total_emails']}, "
        f"Unread: {stats['unread_emails']}, "
        f"Flagged: {stats['flagged_emails']}, "
        f"Total Size: {format_file_size(stats['total_size'] or 0)}"
    )


# Action descriptions
upload_eml_action.short_description = _('Upload EML files')
download_multiple_eml_action.short_description = _('Download as EML/ZIP')
clean_trash_action.short_description = _('Clean trash')
sync_emails_action.short_description = _('Sync emails')
full_sync_emails_action.short_description = _('Full sync emails')
export_email_data_action.short_description = _('Export email data')
get_email_statistics_action.short_description = _('Show statistics')

# Create specific flag actions
mark_as_read_action = bulk_flag_action('seen', True)
mark_as_unread_action = bulk_flag_action('seen', False)
mark_as_flagged_action = bulk_flag_action('flagged', True)
mark_as_unflagged_action = bulk_flag_action('flagged', False)
move_to_trash_action = bulk_flag_action('trash', True)
restore_from_trash_action = bulk_flag_action('trash', False)

# Set descriptions
mark_as_read_action.short_description = _('Mark as read')
mark_as_unread_action.short_description = _('Mark as unread')
mark_as_flagged_action.short_description = _('Mark as flagged')
mark_as_unflagged_action.short_description = _('Mark as unflagged')
move_to_trash_action.short_description = _('Move to trash')
restore_from_trash_action.short_description = _('Restore from trash')


# Advanced search actions
def search_by_sender_action(modeladmin, request, queryset):
    """Action to search emails by sender."""
    
    if not queryset.exists():
        messages.error(request, _('No emails selected'))
        return
    
    # Get unique senders from selection
    senders = set()
    for email in queryset:
        if email.from_address:
            senders.add(email.from_address)
    
    if senders:
        # Create filter for admin changelist
        sender_filter = '|'.join(senders)
        redirect_url = reverse('admin:sage_mailbox_email_changelist')
        redirect_url += f'?from_address__in={sender_filter}'
        
        messages.info(
            request,
            f"Showing emails from {len(senders)} sender(s)"
        )
        
        return HttpResponseRedirect(redirect_url)
    else:
        messages.error(request, _('No senders found in selected emails'))


def search_by_subject_action(modeladmin, request, queryset):
    """Action to search emails by subject keywords."""
    
    if not queryset.exists():
        messages.error(request, _('No emails selected'))
        return
    
    # Extract common keywords from subjects
    keywords = set()
    for email in queryset:
        if email.subject:
            # Simple keyword extraction
            words = email.subject.lower().split()
            for word in words:
                if len(word) > 3:  # Only meaningful words
                    keywords.add(word)
    
    if keywords:
        # Take most common keywords (simple implementation)
        common_keywords = list(keywords)[:5]  # Limit to 5 keywords
        
        messages.info(
            request,
            f"Common keywords found: {', '.join(common_keywords)}"
        )
    else:
        messages.info(request, _('No common keywords found in subjects'))


search_by_sender_action.short_description = _('Search by sender')
search_by_subject_action.short_description = _('Find by subject keywords')


# Maintenance actions
def cleanup_orphaned_attachments_action(modeladmin, request, queryset):
    """Action to cleanup orphaned attachments."""
    
    from django.db import transaction
    
    orphaned_count = 0
    
    with transaction.atomic():
        for attachment in queryset:
            if not attachment.email_id:
                attachment.delete()
                orphaned_count += 1
    
    if orphaned_count > 0:
        messages.success(
            request,
            f"Cleaned up {orphaned_count} orphaned attachment(s)"
        )
    else:
        messages.info(request, _('No orphaned attachments found'))


def verify_attachment_integrity_action(modeladmin, request, queryset):
    """Action to verify attachment file integrity."""
    
    missing_files = 0
    corrupted_files = 0
    
    for attachment in queryset:
        try:
            if attachment.file_path:
                # Check if file exists
                if not attachment.file_path.storage.exists(attachment.file_path.name):
                    missing_files += 1
                    continue
                
                # Verify checksum if available
                if attachment.checksum:
                    import hashlib
                    with attachment.file_path.open('rb') as f:
                        content = f.read()
                        calculated_checksum = hashlib.sha256(content).hexdigest()
                        
                        if calculated_checksum != attachment.checksum:
                            corrupted_files += 1
        except Exception as e:
            messages.warning(
                request,
                f"Error checking attachment {attachment.filename}: {e}"
            )
    
    if missing_files > 0 or corrupted_files > 0:
        messages.warning(
            request,
            f"Found {missing_files} missing and {corrupted_files} corrupted file(s)"
        )
    else:
        messages.success(request, _('All attachment files are intact'))


cleanup_orphaned_attachments_action.short_description = _('Cleanup orphaned attachments')
verify_attachment_integrity_action.short_description = _('Verify file integrity') 