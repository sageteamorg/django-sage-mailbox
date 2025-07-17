"""
Mailbox-related admin actions for sage_mailbox.

This module contains admin actions specifically for mailbox management,
including trash cleaning and mailbox operations.
"""

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.forms import Form, IntegerField, BooleanField
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from ...models import Email, Mailbox


class CleanTrashForm(Form):
    """Form for cleaning trash."""
    
    days_old = IntegerField(
        min_value=1,
        max_value=365,
        initial=30,
        label=_('Days old'),
        help_text=_('Delete emails older than this many days')
    )
    
    confirm = BooleanField(
        label=_('Confirm permanent deletion'),
        help_text=_('This action cannot be undone'),
        required=True
    )


def clean_trash_action(modeladmin, request, queryset):
    """
    Action to clean trash by permanently deleting old emails.
    
    This action permanently deletes emails from the trash that are older
    than the specified number of days. This operation cannot be undone.
    """
    
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


# Action descriptions for admin
clean_trash_action.short_description = _('Clean trash (permanent deletion)') 