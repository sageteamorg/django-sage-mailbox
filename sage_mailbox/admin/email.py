from collections import OrderedDict
import logging
import time
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import path, reverse
from django.urls.resolvers import URLPattern
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from sage_imap.helpers.enums import Flag, FlagCommand
from sage_imap.helpers.search import IMAPSearchCriteria
from sage_imap.models.message import MessageSet
from sage_imap.services import IMAPClient, IMAPMailboxUIDService

from sage_mailbox.admin.actions import (
    download_as_eml,
    mark_as_flagged,
    mark_as_read,
    mark_as_unflagged,
    mark_as_unread,
    move_to_trash,
    restore_from_trash,
)
from sage_mailbox.models import Attachment, EmailMessage, Junk, Sent, Trash
from sage_mailbox.models.mailbox import Mailbox, StandardMailboxNames
from sage_mailbox.repository.service import EmailSyncService

logger = logging.getLogger(__name__)


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0

    fields = [
        "filename",
        "file",
        "content_type",
        "content_transfer_encoding",
    ]
    readonly_fields = (
        "content_type",
        "content_transfer_encoding",
    )


@admin.register(EmailMessage)
class EmailMessageAdmin(admin.ModelAdmin):
    change_list_template = "admin/email/change_list.html"
    list_display = (
        "id",
        "uid",
        "get_message_id",
        "subject",
        "get_from_address",
        "has_attachment",
        "total_attachments",
        "is_read",
        "is_flagged",
        "mailbox",
        "date",
        "modified_at",
    )
    search_fields = (
        "subject",
        "from_address",
        "to_address",
        "cc_address",
        "bcc_address",
        "message_id",
    )
    list_select_related = ("mailbox",)
    save_on_top = True
    search_help_text = mark_safe(
        _(
            "Search is available for the following fields:<br>"
            "<ul>"
            "<li><strong>Subject</strong>: The subject line of the email.</li>"
            "<li><strong>From Address</strong>: The email address of the sender.</li>"
            "<li><strong>To Address</strong>: The email addresses of the primary recipients.</li>"
            "<li><strong>CC Address</strong>: The email addresses of the carbon copy recipients.</li>"
            "<li><strong>BCC Address</strong>: The email addresses of the blind carbon copy recipients.</li>"
            "<li><strong>Message ID</strong>: The unique identifier of the email message.</li>"
            "</ul>"
        )
    )
    actions = (
        mark_as_read,
        mark_as_unread,
        mark_as_flagged,
        mark_as_unflagged,
        download_as_eml,
        move_to_trash,
    )
    list_filter = ("date", "mailbox", "is_read", "is_flagged", "modified_at")
    readonly_fields = (
        "uid",
        "date",
        "message_id",
        "from_address",
        "mailbox",
        "flags",
        "is_read",
        "is_flagged",
        "size",
    )
    fieldsets = (
        (
            "Identifiers",
            {
                "fields": (
                    "uid",
                    "message_id",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Email Information",
            {
                "fields": (
                    "subject",
                    "from_address",
                    "to_address",
                    "plain_body",
                    "html_body",
                )
            },
        ),
        (
            "Carbon Copy",
            {
                "fields": (
                    "cc_address",
                    "bcc_address",
                )
            },
        ),
        (
            "Email Status",
            {
                "fields": (
                    "is_read",
                    "is_flagged",
                    "flags",
                    "size",
                    "mailbox",
                    "date",
                    "headers",
                )
            },
        ),
    )
    inlines = [AttachmentInline]

    @admin.display(
        ordering="created_at",
        description=_("Recently Created"),
        empty_value=_("Not Recent"),
    )
    def is_recent(self, obj):
        return obj.created_at >= datetime.now() - timedelta(days=7)

    @admin.display(
        boolean=True, ordering="has_attachments", description=_("Has Attachment")
    )
    def has_attachment(self, obj):
        return obj.has_attachments

    @admin.display(ordering="total_attachments", description=_("Total Attachments"))
    def total_attachments(self, obj):
        return obj.total_attachments

    @admin.display(ordering="from_address", description=_("From Address"))
    def get_from_address(self, obj):
        return format_html(
            '<div style="max-width: 130px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{}</div>',
            obj.from_address,
        )

    @admin.display(ordering="message_id", description=_("Message-ID"))
    def get_message_id(self, obj):
        return format_html(
            '<div style="max-width: 130px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{}</div>',
            obj.message_id,
        )

    def get_actions(self, request: HttpRequest) -> OrderedDict[Any, Any]:
        actions = super().get_actions(request)

        # If the user is a superuser, return all actions
        if request.user.is_superuser:
            return actions

        # Define a dictionary mapping permissions to actions
        permission_action_map = {
            "mark_read": "mark_as_read",
            "mark_unread": "mark_as_unread",
            "flag_email": "mark_as_flagged",
            "unflag_email": "mark_as_unflagged",
            "download_eml": "download_as_eml",
        }

        # Remove actions the user does not have permission for
        for perm, action in permission_action_map.items():
            if not request.user.has_perm(f"sage_mailbox.{perm}"):
                actions.pop(action, None)

        return actions

    def get_readonly_fields(
        self, request: HttpRequest, obj: Any | None = ...
    ) -> list[str] | tuple[Any, ...]:
        if obj:
            readonly_fields = (
                "uid",
                "message_id",
                "subject",
                "from_address",
                "to_address",
                "cc_address",
                "bcc_address",
                "date",
                "raw",
                "plain_body",
                "html_body",
                "flags",
                # "headers",
                "mailbox",
                "is_read",
                "is_flagged",
                "size",
            )
            return readonly_fields
        return super().get_readonly_fields(request, obj)

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)
        return qs.select_related_mailbox().total_attachments().has_attachments()

    def get_urls(self) -> list[URLPattern]:
        urls = super().get_urls()
        custom_urls = [
            path(
                "sync-emails/",
                self.admin_site.admin_view(self.sync_emails),
                name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_sync",
            ),
        ]
        return custom_urls + urls

    def sync_emails(self, request):
        start_time = time.time()

        imap_host = settings.IMAP_SERVER_DOMAIN
        imap_username = settings.IMAP_SERVER_USER
        imap_password = settings.IMAP_SERVER_PASSWORD

        mailbox_name = Mailbox.objects.get(
            folder_type=StandardMailboxNames.INBOX
        ).folder_type

        try:
            # Try to get the mailbox
            mailbox = Mailbox.objects.get(folder_type=mailbox_name)
        except ObjectDoesNotExist:
            # If the mailbox does not exist, show a user-friendly message
            message = "The INBOX mailbox does not exist. Please sync mailboxes first, then sync emails."
            messages.add_message(request, messages.WARNING, message)

            # Redirect to the admin change list URL
            change_list_url = reverse(
                f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_changelist"
            )
            return redirect(change_list_url)

        # Proceed with email synchronization if the mailbox exists
        service = EmailSyncService(imap_host, imap_username, imap_password)
        result = service.fetch_and_save_emails(mailbox.name)

        end_time = time.time()
        runtime = end_time - start_time

        created_emails = result.get("created_emails", 0)
        created_attachments = result.get("created_attachments", 0)

        # Create a message to display in the admin interface
        message = f"Email synchronization completed: {created_emails} emails and {created_attachments} attachments created in {runtime:.2f} seconds."

        # Set the message in Django's messages framework
        messages.add_message(request, messages.INFO, message)

        # Redirect to the change list URL
        change_list_url = reverse(
            f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_changelist"
        )
        return redirect(change_list_url)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        email_message = self.get_object(request, object_id)
        if email_message and not email_message.is_read:
            try:
                host = settings.IMAP_SERVER_DOMAIN
                username = settings.IMAP_SERVER_USER
                password = settings.IMAP_SERVER_PASSWORD

                with IMAPClient(host, username, password) as client:
                    with IMAPMailboxUIDService(client) as mailbox:
                        mailbox.select(email_message.mailbox.name)

                        status, data = client.uid(
                            "STORE", str(email_message.uid), "+FLAGS", "\\Seen"
                        )
                        logger.debug(
                            f"Marked email with UID {email_message.uid} as SEEN on IMAP server."
                        )

                        email_message.is_read = True
                        email_message.save(update_fields=["is_read"])
                        logger.debug(
                            f"Marked email message object {email_message.pk} as read in the database."
                        )
                        messages.success(request, _("Email marked as read."))
            except Exception as e:
                logger.error(
                    f"Error marking email message {email_message.pk} as read: {str(e)}",
                    exc_info=True,
                )
                messages.error(
                    request, _("Failed to mark the email as read on the IMAP server.")
                )
        return super().change_view(request, object_id, form_url, extra_context)


@admin.register(Sent)
class SentAdmin(EmailMessageAdmin):

    actions = (download_as_eml,)

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)
        return (
            qs.select_related_mailbox()
            .total_attachments()
            .has_attachments()
            .filter(mailbox__folder_type=StandardMailboxNames.SENT)
        )

    def get_urls(self) -> list[URLPattern]:
        urls = super().get_urls()
        custom_urls = [
            path(
                "sync-emails/sent/",
                self.admin_site.admin_view(self.sync_emails),
                name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_sync",
            ),
        ]
        total = custom_urls + urls
        return total


@admin.register(Junk)
class JunkAdmin(EmailMessageAdmin):

    actions = (download_as_eml,)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        return False

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)
        return (
            qs.select_related_mailbox()
            .total_attachments()
            .has_attachments()
            .filter(mailbox__folder_type=StandardMailboxNames.SENT)
        )

    def get_urls(self) -> list[URLPattern]:
        urls = super().get_urls()
        custom_urls = [
            path(
                "sync-emails/junk/",
                self.admin_site.admin_view(self.sync_emails),
                name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_sync",
            ),
        ]
        total = custom_urls + urls
        return total


@admin.register(Trash)
class TrashAdmin(EmailMessageAdmin):

    actions = (download_as_eml, restore_from_trash)

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)
        return (
            qs.select_related_mailbox()
            .total_attachments()
            .has_attachments()
            .filter(mailbox__folder_type=StandardMailboxNames.TRASH)
        )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        return False

    def get_urls(self) -> list[URLPattern]:
        urls = super().get_urls()
        custom_urls = [
            path(
                "sync-emails/trash/",
                self.admin_site.admin_view(self.sync_emails),
                name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_sync",
            ),
            path(
                "clear-trash/",
                self.admin_site.admin_view(self.clear_trash),
                name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_clear",
            ),
        ]
        total = custom_urls + urls
        return total

    @transaction.atomic
    def clear_trash(self, request: HttpRequest):
        start_time = time.time()
        try:
            host = settings.IMAP_SERVER_DOMAIN
            username = settings.IMAP_SERVER_USER
            password = settings.IMAP_SERVER_PASSWORD

            with IMAPClient(host, username, password) as client:
                trash_mailbox = Mailbox.objects.get(
                    folder_type=StandardMailboxNames.TRASH
                )
                mailbox_service = IMAPMailboxUIDService(client)
                mailbox_service.select(trash_mailbox.name)
                email_ids = mailbox_service.uid_search(
                    IMAPSearchCriteria.ALL, charset=None
                )
                client.uid(
                    "STORE",
                    MessageSet(email_ids).msg_ids,
                    FlagCommand.ADD,
                    Flag.DELETED,
                )
                mailbox_service.uid_delete(MessageSet(email_ids), trash_mailbox.name)

                EmailMessage.objects.filter(
                    mailbox__folder_type=StandardMailboxNames.TRASH
                ).delete()
                logger.debug("Permanently deleted email messages from the database.")

            end_time = time.time()
            runtime = end_time - start_time
            self.message_user(
                request,
                _("Successfully permanently deleted emails in {:.2f} seconds.").format(
                    runtime
                ),
                messages.SUCCESS,
            )

        except Exception as e:
            end_time = time.time()
            runtime = end_time - start_time
            logger.error(f"Error clearing trash: {str(e)}", exc_info=True)
            self.message_user(
                request,
                _(
                    "Failed to clear trash. Please try again. Task completed in {:.2f} seconds."
                ).format(runtime),
                messages.ERROR,
            )

        change_list_url = reverse(
            f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_changelist"
        )
        return HttpResponseRedirect(change_list_url)
