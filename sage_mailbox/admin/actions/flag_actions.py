"""
Flag-related admin actions for sage_mailbox.

This module contains admin actions specifically for email flag management,
including bulk flag operations and status changes.
"""

from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from ...models import Email


def bulk_flag_action(flag_type, flag_value):
    """
    Generate bulk flag action.
    
    This function creates admin actions for bulk flag operations
    such as marking emails as read/unread, flagged/unflagged, etc.
    
    Args:
        flag_type: Type of flag ('seen', 'flagged', 'trash', etc.)
        flag_value: Boolean value to set for the flag
    
    Returns:
        Admin action function
    """
    
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


# Create specific flag actions
mark_read_action = bulk_flag_action('seen', True)
mark_unread_action = bulk_flag_action('seen', False)
mark_flagged_action = bulk_flag_action('flagged', True)
mark_unflagged_action = bulk_flag_action('flagged', False)
move_to_trash_action = bulk_flag_action('trash', True)
restore_from_trash_action = bulk_flag_action('trash', False)

# Action descriptions for admin
mark_read_action.short_description = _('Mark as read')
mark_unread_action.short_description = _('Mark as unread')
mark_flagged_action.short_description = _('Mark as flagged')
mark_unflagged_action.short_description = _('Mark as unflagged')
move_to_trash_action.short_description = _('Move to trash')
restore_from_trash_action.short_description = _('Restore from trash') 