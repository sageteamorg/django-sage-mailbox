"""
Email-related admin actions for sage_mailbox.

This module contains admin actions specifically for email management,
including upload, download, synchronization, and bulk operations.
"""

import zipfile
from io import BytesIO
from typing import List, Tuple

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.core.files.uploadedfile import UploadedFile
from django.forms import FileField, Form, ModelForm, ModelChoiceField, ValidationError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from sage_mailbox.models import Email, Mailbox, Attachment
from sage_mailbox.utils import FileUtils, EmailUtils, format_file_size
from sage_mailbox.utils.validators import validate_filename

from sage_imap.models.email import EmailMessage as SageEmailMessage


class UploadEMLForm(Form):
    """Form for uploading EML files."""
    
    mailbox = ModelChoiceField(
        queryset=Mailbox.objects.all(),
        label=_('Mailbox'),
        help_text=_('Select the mailbox to upload emails to'),
        required=True
    )
    
    eml_file = FileField(
        label=_('EML File'),
        help_text=_('Select .eml file or .zip archive containing .eml files'),
        required=True
    )
    
    def clean_eml_file(self):
        """Validate uploaded file."""
        file = self.cleaned_data.get('eml_file')
        
        if not file:
            raise ValidationError(_('No file selected'))
        
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
        
        return file


def upload_eml_action(modeladmin, request, queryset):
    """
    Action to upload EML files to mailbox.
    
    This action allows administrators to upload .eml files or .zip archives
    containing .eml files to selected mailboxes.
    """
    
    if 'apply' in request.POST:
        form = UploadEMLForm(request.POST, request.FILES)
        
        if form.is_valid():
            mailbox_id = form.cleaned_data['mailbox']
            mailbox = Mailbox.objects.get(id=mailbox_id)
            file = form.cleaned_data['eml_file']
            
            uploaded_count = 0
            errors = []
            
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
    """
    Action to download multiple emails as ZIP.
    
    This action allows downloading selected emails as .eml files
    in a ZIP archive for backup or analysis purposes.
    """
    
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


def sync_emails_action(modeladmin, request, queryset):
    """
    Action to synchronize emails from IMAP server.
    
    This action synchronizes emails from the IMAP server for selected
    mailboxes using the sage_imap library.
    """
    
    sync_count = 0
    errors = []
    
    for mailbox in queryset:
        try:
            # Use sage_imap to sync emails
            count = Email.objects.sync_from_imap(mailbox)
            sync_count += count
        except Exception as e:
            errors.append(f"Failed to sync {mailbox.name}: {e}")
    
    if sync_count > 0:
        messages.success(
            request,
            f"Successfully synchronized {sync_count} email(s)"
        )
    
    for error in errors:
        messages.error(request, error)
    
    if not sync_count and not errors:
        messages.info(request, _('No new emails found'))


def full_sync_emails_action(modeladmin, request, queryset):
    """
    Action to perform full synchronization of emails.
    
    This action performs a complete synchronization of all emails
    from the IMAP server, including re-downloading existing emails.
    """
    
    sync_count = 0
    errors = []
    
    for mailbox in queryset:
        try:
            # Use sage_imap to perform full sync
            count = Email.objects.full_sync_from_imap(mailbox)
            sync_count += count
        except Exception as e:
            errors.append(f"Failed to full sync {mailbox.name}: {e}")
    
    if sync_count > 0:
        messages.success(
            request,
            f"Successfully synchronized {sync_count} email(s) (full sync)"
        )
    
    for error in errors:
        messages.error(request, error)
    
    if not sync_count and not errors:
        messages.info(request, _('No emails found for synchronization'))


def export_email_data_action(modeladmin, request, queryset):
    """
    Action to export email data as CSV.
    
    This action exports selected emails' metadata as a CSV file
    for analysis or reporting purposes.
    """
    
    import csv
    from django.http import HttpResponse
    from django.utils.timezone import now
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="emails_export_{now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Subject', 'From Address', 'From Name', 'To Addresses', 'CC Addresses',
        'Date', 'Size', 'Mailbox', 'UID', 'Is Seen', 'Is Flagged', 'Is Deleted',
        'Priority', 'Is Outgoing', 'Send Status'
    ])
    
    for email in queryset:
        writer.writerow([
            email.subject,
            email.from_address,
            email.from_name,
            ', '.join(email.to_addresses) if email.to_addresses else '',
            ', '.join(email.cc_addresses) if email.cc_addresses else '',
            email.date.strftime('%Y-%m-%d %H:%M:%S') if email.date else '',
            email.size,
            email.mailbox.name,
            email.uid,
            email.is_seen,
            email.is_flagged,
            email.is_deleted,
            email.priority,
            email.is_outgoing,
            email.send_status
        ])
    
    return response


def get_email_statistics_action(modeladmin, request, queryset):
    """
    Action to get email statistics.
    
    This action displays statistics about selected emails
    including counts, sizes, and distribution information.
    """
    
    from django.db.models import Count, Sum, Avg
    
    stats = queryset.aggregate(
        total_count=Count('id'),
        total_size=Sum('size'),
        avg_size=Avg('size'),
        seen_count=Count('id', filter=models.Q(is_seen=True)),
        flagged_count=Count('id', filter=models.Q(is_flagged=True)),
        deleted_count=Count('id', filter=models.Q(is_deleted=True)),
        attachment_count=Count('attachments')
    )
    
    messages.info(
        request,
        f"Email Statistics: {stats['total_count']} total emails, "
        f"{format_file_size(stats['total_size'] or 0)} total size, "
        f"{stats['seen_count']} read, {stats['flagged_count']} flagged, "
        f"{stats['deleted_count']} deleted, {stats['attachment_count']} attachments"
    )


def search_by_sender_action(modeladmin, request, queryset):
    """
    Action to search emails by sender.
    
    This action filters emails by sender address and displays
    the results in a new admin page.
    """
    
    if not queryset.exists():
        messages.error(request, _('No emails selected'))
        return
    
    # Get unique senders from selected emails
    senders = queryset.values_list('from_address', flat=True).distinct()
    
    # Find all emails from these senders
    all_emails = Email.objects.filter(from_address__in=senders)
    
    messages.info(
        request,
        f"Found {all_emails.count()} emails from {len(senders)} unique sender(s)"
    )
    
    # Redirect to filtered email list
    from django.urls import reverse
    from urllib.parse import urlencode
    
    params = urlencode({'from_address__in': ','.join(senders)})
    url = reverse('admin:sage_mailbox_email_changelist')
    return HttpResponseRedirect(f"{url}?{params}")


def search_by_subject_action(modeladmin, request, queryset):
    """
    Action to search emails by subject.
    
    This action finds emails with similar subjects and displays
    the results for thread analysis.
    """
    
    if not queryset.exists():
        messages.error(request, _('No emails selected'))
        return
    
    # Get unique subjects from selected emails
    subjects = queryset.values_list('subject', flat=True).distinct()
    
    # Find all emails with similar subjects
    from django.db.models import Q
    
    query = Q()
    for subject in subjects:
        if subject:
            query |= Q(subject__icontains=subject)
    
    all_emails = Email.objects.filter(query)
    
    messages.info(
        request,
        f"Found {all_emails.count()} emails with similar subjects"
    )
    
    # Redirect to filtered email list
    from django.urls import reverse
    from urllib.parse import urlencode
    
    params = urlencode({'subject__icontains': ' OR '.join(subjects)})
    url = reverse('admin:sage_mailbox_email_changelist')
    return HttpResponseRedirect(f"{url}?{params}")


# Action descriptions for admin
upload_eml_action.short_description = _('Upload EML files')
download_multiple_eml_action.short_description = _('Download as EML/ZIP')
sync_emails_action.short_description = _('Sync from IMAP')
full_sync_emails_action.short_description = _('Full sync from IMAP')
export_email_data_action.short_description = _('Export as CSV')
get_email_statistics_action.short_description = _('Show statistics')
search_by_sender_action.short_description = _('Search by sender')
search_by_subject_action.short_description = _('Search by subject') 