import time

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.urls import path, reverse
from django.urls.resolvers import URLPattern

from sage_mailbox.models import Mailbox
from sage_mailbox.repository.service import EmailSyncService

imap_host = settings.IMAP_SERVER_DOMAIN
imap_username = settings.IMAP_SERVER_USER
imap_password = settings.IMAP_SERVER_PASSWORD


class EmailSyncMixin:
    mailbox_name = None

    def get_urls(self) -> list[URLPattern]:
        urls = super().get_urls()
        custom_urls = [
            path(
                "sync-emails/",
                self.admin_site.admin_view(self.sync_emails),
                name=(
                    f"{self.model._meta.app_label}_"
                    f"{self.model._meta.model_name}_sync"
                ),
            ),
        ]
        return custom_urls + urls

    def sync_emails(self, request):
        start_time = time.time()

        try:
            mailbox = Mailbox.objects.get(folder_type=self.mailbox_name)
        except ObjectDoesNotExist:
            message = (
                f"The {self.mailbox_name} mailbox does not exist. "
                "Please sync mailboxes first, then sync emails."
            )
            messages.add_message(request, messages.WARNING, message)
            change_list_url = reverse(
                f"admin:{self.model._meta.app_label}_"
                f"{self.model._meta.model_name}_changelist"
            )
            return redirect(change_list_url)

        service = EmailSyncService(imap_host, imap_username, imap_password)
        result = service.fetch_and_save_emails(mailbox.name)

        end_time = time.time()
        runtime = end_time - start_time

        created_emails = result.get("created_emails", 0)
        created_attachments = result.get("created_attachments", 0)

        message = (
            f"Email synchronization completed: {created_emails} emails and "
            f"{created_attachments} attachments created in {runtime:.2f} seconds."
        )
        messages.add_message(request, messages.INFO, message)

        change_list_url = reverse(
            f"admin:{self.model._meta.app_label}_"
            f"{self.model._meta.model_name}_changelist"
        )
        return redirect(change_list_url)
