"""
Custom admin site configuration for sage_mailbox.

This module provides a custom admin site with specialized organization
and styling for email management functionality.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from ..models import IMAPServer, SMTPServer, EmailTemplate, Mailbox, Email, Attachment, EmailFlag
from .server_admin import IMAPServerAdmin, SMTPServerAdmin
from .template_admin import EmailTemplateAdmin
from .mailbox_admin import MailboxAdmin
from .email_admin import EmailAdmin
from .attachment_admin import AttachmentAdmin, EmailFlagAdmin


class MailboxAdminSite(admin.AdminSite):
    """Custom admin site for sage_mailbox with sage_imap integration."""
    
    site_header = _('Sage Mailbox Administration (sage_imap)')
    site_title = _('Sage Mailbox Admin')
    index_title = _('Email Management Dashboard with sage_imap')
    
    def get_app_list(self, request):
        """Customize app list for better organization."""
        app_list = super().get_app_list(request)
        
        # Reorganize models
        for app in app_list:
            if app['app_label'] == 'sage_mailbox':
                # Reorder models
                model_order = [
                    'IMAPServer', 'SMTPServer', 'EmailTemplate', 
                    'Mailbox', 'Email', 'Attachment', 'EmailFlag'
                ]
                app['models'] = sorted(
                    app['models'],
                    key=lambda x: model_order.index(x['object_name']) if x['object_name'] in model_order else 999
                )
        
        return app_list


# Create instance of custom admin site
mailbox_admin_site = MailboxAdminSite(name='mailbox_admin')

# Register models with custom admin site
mailbox_admin_site.register(IMAPServer, IMAPServerAdmin)
mailbox_admin_site.register(SMTPServer, SMTPServerAdmin)
mailbox_admin_site.register(EmailTemplate, EmailTemplateAdmin)
mailbox_admin_site.register(Mailbox, MailboxAdmin)
mailbox_admin_site.register(Email, EmailAdmin)
mailbox_admin_site.register(Attachment, AttachmentAdmin)
mailbox_admin_site.register(EmailFlag, EmailFlagAdmin) 