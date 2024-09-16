import logging
import time
import zipfile
from io import BytesIO

from django.conf import settings
from django.contrib import admin, messages
from django.db import transaction
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
from sage_imap.helpers.enums import Flag, FlagCommand
from sage_imap.models.message import MessageSet
from sage_imap.services import IMAPClient, IMAPMailboxUIDService

from sage_mailbox.models.mailbox import Mailbox, StandardMailboxNames

logger = logging.getLogger(__name__)


@admin.action(description=_("Move selected emails to trash"))
@transaction.atomic
def move_to_trash(modeladmin, request, queryset):
    start_time = time.time()
    emails_to_delete = []

    host = settings.IMAP_SERVER_DOMAIN
    username = settings.IMAP_SERVER_USER
    password = settings.IMAP_SERVER_PASSWORD

    try:
        with IMAPClient(host, username, password) as imap_client:
            imap_mailbox_service = IMAPMailboxUIDService(imap_client)
            trash_mailbox = Mailbox.objects.get(folder_type=StandardMailboxNames.TRASH)

            for email in queryset:
                imap_mailbox_service.select(email.mailbox.name)
                imap_mailbox_service.uid_trash(
                    MessageSet(str(email.uid)), trash_mailbox.name
                )
                emails_to_delete.append(email)
                logger.debug("Moved email with UID %s to trash.", email.uid)

            queryset.model.objects.filter(
                id__in=[email.id for email in emails_to_delete]
            ).delete()
            logger.debug("Deleted moved email messages from the database.")

        end_time = time.time()
        runtime = end_time - start_time
        messages.success(
            request,
            _(
                "Successfully moved {} emails to trash and deleted them "
                "from the database in {:.2f} seconds."
            ).format(len(emails_to_delete), runtime),
        )

    except Exception as exc:
        end_time = time.time()
        runtime = end_time - start_time
        logger.error(
            "Error moving email messages to trash: %s", str(exc), exc_info=True
        )
        messages.error(
            request,
            _(
                "Failed to move some emails to trash. Please try again. "
                "Task completed in {:.2f} seconds."
            ).format(runtime),
        )
        transaction.set_rollback(True)


@admin.action(description=_("Mark selected emails as read"))
@transaction.atomic
def mark_as_read(modeladmin, request, queryset):
    start_time = time.time()
    email_messages_to_update = []

    host = settings.IMAP_SERVER_DOMAIN
    username = settings.IMAP_SERVER_USER
    password = settings.IMAP_SERVER_PASSWORD

    try:
        with IMAPClient(host, username, password) as client:
            mailbox = IMAPMailboxUIDService(client)

            for email_message in queryset:
                mailbox.select(email_message.mailbox.name)
                if not email_message.is_read:
                    status, data = client.uid(
                        "STORE", str(email_message.uid), "+FLAGS", "\\Seen"
                    )
                    logger.debug("Marked email with UID %s as SEEN.", email_message.uid)

                    email_message.is_read = True
                    email_messages_to_update.append(email_message)
                    logger.debug(
                        "Prepared to mark email message "
                        "object %s as read in the database.",
                        email_message.pk,
                    )

        queryset.model.objects.bulk_update(email_messages_to_update, ["is_read"])
        logger.debug("Bulk updated all email messages to read status in the database.")

        end_time = time.time()
        runtime = end_time - start_time
        messages.success(
            request,
            _("Successfully marked {} emails as read in {:.2f} seconds.").format(
                len(email_messages_to_update), runtime
            ),
        )

    except Exception as exc:
        end_time = time.time()
        runtime = end_time - start_time
        logger.error(
            "Error marking email messages as read: %s", str(exc), exc_info=True
        )
        messages.error(
            request,
            _(
                "Failed to mark some emails as read. Please try again. "
                "Task completed in {:.2f} seconds."
            ).format(runtime),
        )
        transaction.set_rollback(True)


@admin.action(description=_("Mark selected emails as unread"))
@transaction.atomic
def mark_as_unread(modeladmin, request, queryset):
    start_time = time.time()
    email_messages_to_update = []

    host = settings.IMAP_SERVER_DOMAIN
    username = settings.IMAP_SERVER_USER
    password = settings.IMAP_SERVER_PASSWORD

    try:
        with IMAPClient(host, username, password) as client:
            mailbox = IMAPMailboxUIDService(client)

            for email_message in queryset:
                mailbox.select(email_message.mailbox.name)
                if email_message.is_read:
                    # TODO: python-sage-imap does not support uid on flag service
                    status, data = client.uid(
                        "STORE", str(email_message.uid), FlagCommand.REMOVE, Flag.SEEN
                    )
                    logger.debug(
                        "Unmarked email with Message-ID %s as SEEN.", email_message.uid
                    )

                    email_message.is_read = False
                    email_messages_to_update.append(email_message)
                    logger.debug(
                        "Prepared to mark email message "
                        "object %s as unread in the database.",
                        email_message.pk,
                    )

        queryset.model.objects.bulk_update(email_messages_to_update, ["is_read"])
        logger.debug(
            "Bulk updated all email messages to unread status in the database."
        )

        end_time = time.time()
        runtime = end_time - start_time
        messages.success(
            request,
            _("Successfully marked {} emails as unread in {:.2f} seconds.").format(
                len(email_messages_to_update), runtime
            ),
        )

    except Exception as exc:
        end_time = time.time()
        runtime = end_time - start_time
        logger.error(
            "Error marking email messages as unread: %s", str(exc), exc_info=True
        )
        messages.error(
            request,
            _(
                "Failed to mark some emails as unread. Please try again. "
                "Task completed in {:.2f} seconds."
            ).format(runtime),
        )
        transaction.set_rollback(True)


@admin.action(description=_("Mark selected emails as flagged"))
@transaction.atomic
def mark_as_flagged(modeladmin, request, queryset):
    start_time = time.time()
    email_messages_to_update = []

    host = settings.IMAP_SERVER_DOMAIN
    username = settings.IMAP_SERVER_USER
    password = settings.IMAP_SERVER_PASSWORD

    try:
        with IMAPClient(host, username, password) as client:
            mailbox = IMAPMailboxUIDService(client)

            for email_message in queryset:
                mailbox.select(email_message.mailbox.name)
                if not email_message.is_flagged:
                    status, data = client.uid(
                        "STORE", str(email_message.uid), "+FLAGS", "\\Flagged"
                    )
                    logger.debug(
                        "Marked email with UID %s as FLAGGED.", email_message.uid
                    )

                    email_message.is_flagged = True
                    email_messages_to_update.append(email_message)
                    logger.debug(
                        "Prepared to mark email message "
                        "object %s as flagged in the database.",
                        email_message.pk,
                    )

        queryset.model.objects.bulk_update(email_messages_to_update, ["is_flagged"])
        logger.debug(
            "Bulk updated all email messages to flagged status in the database."
        )

        end_time = time.time()
        runtime = end_time - start_time
        messages.success(
            request,
            _("Successfully marked {} emails as flagged in {:.2f} seconds.").format(
                len(email_messages_to_update), runtime
            ),
        )

    except Exception as exc:
        end_time = time.time()
        runtime = end_time - start_time
        logger.error(
            "Error marking email messages as flagged: %s", str(exc), exc_info=True
        )
        messages.error(
            request,
            _(
                "Failed to mark some emails as flagged. Please try again. "
                "Task completed in {:.2f} seconds."
            ).format(runtime),
        )
        transaction.set_rollback(True)


@admin.action(description=_("Mark selected emails as unflagged"))
@transaction.atomic
def mark_as_unflagged(modeladmin, request, queryset):
    start_time = time.time()
    email_messages_to_update = []

    host = settings.IMAP_SERVER_DOMAIN
    username = settings.IMAP_SERVER_USER
    password = settings.IMAP_SERVER_PASSWORD

    try:
        with IMAPClient(host, username, password) as client:
            mailbox = IMAPMailboxUIDService(client)

            for email_message in queryset:
                mailbox.select(email_message.mailbox.name)
                if email_message.is_flagged:
                    status, data = client.uid(
                        "STORE", str(email_message.uid), "-FLAGS", "\\Flagged"
                    )
                    logger.debug(
                        "Unmarked email with UID %s as FLAGGED.", email_message.uid
                    )

                    email_message.is_flagged = False
                    email_messages_to_update.append(email_message)
                    logger.debug(
                        "Prepared to mark email message "
                        "object %s as unflagged in the database.",
                        email_message.pk,
                    )

        queryset.model.objects.bulk_update(email_messages_to_update, ["is_flagged"])
        logger.debug(
            "Bulk updated all email messages to unflagged status in the database."
        )

        end_time = time.time()
        runtime = end_time - start_time
        messages.success(
            request,
            _("Successfully marked {} emails as unflagged in {:.2f} seconds.").format(
                len(email_messages_to_update), runtime
            ),
        )

    except Exception as exc:
        end_time = time.time()
        runtime = end_time - start_time
        logger.error(
            "Error marking email messages as unflagged: %s", str(exc), exc_info=True
        )
        messages.error(
            request,
            _(
                "Failed to mark some emails as unflagged. Please try again. "
                "Task completed in {:.2f} seconds."
            ).format(runtime),
        )
        transaction.set_rollback(True)


@admin.action(description=_("Download selected emails as EML"))
def download_as_eml(modeladmin, request, queryset):
    start_time = time.time()
    email_files = []

    try:
        for email_message in queryset:
            if email_message.raw:
                email_files.append((f"{email_message.uid}.eml", email_message.raw))
                logger.debug(
                    "Added raw data for email with Message-ID %s.", email_message.uid
                )

        if len(email_files) == 1:
            response = HttpResponse(email_files[0][1], content_type="message/rfc822")
            response[
                "Content-Disposition"
            ] = f'attachment; filename="{email_files[0][0]}"'
            logger.debug("Prepared single EML file for download: %s", email_files[0][0])
        else:
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                for file_name, eml_data in email_files:
                    zip_file.writestr(file_name, eml_data)
                    logger.debug("Added %s to zip file.", file_name)

            zip_buffer.seek(0)
            response = HttpResponse(zip_buffer, content_type="application/zip")
            response["Content-Disposition"] = 'attachment; filename="emails.zip"'
            logger.debug(
                "Prepared zip file for download containing multiple EML files."
            )

        end_time = time.time()
        runtime = end_time - start_time
        messages.success(
            request,
            _("Successfully prepared download for {} emails in {:.2f} seconds.").format(
                len(email_files), runtime
            ),
        )
        return response

    except Exception as exc:
        logger.error("An error occurred while preparing the EML files: %s", str(exc))
        messages.error(request, _("An error occurred while preparing the EML files."))
        return None


@admin.action(description=_("Restore selected emails from trash to inbox"))
@transaction.atomic
def restore_from_trash(modeladmin, request, queryset):
    start_time = time.time()
    emails_to_restore = []

    host = settings.IMAP_SERVER_DOMAIN
    username = settings.IMAP_SERVER_USER
    password = settings.IMAP_SERVER_PASSWORD

    try:
        with IMAPClient(host, username, password) as imap_client:
            imap_mailbox_service = IMAPMailboxUIDService(imap_client)
            trash_mailbox = Mailbox.objects.get(folder_type=StandardMailboxNames.TRASH)
            inbox_mailbox = Mailbox.objects.get(folder_type=StandardMailboxNames.INBOX)

            for email in queryset:
                imap_mailbox_service.select(trash_mailbox.name)
                imap_mailbox_service.uid_restore(
                    MessageSet(str(email.uid)), trash_mailbox.name, inbox_mailbox.name
                )
                emails_to_restore.append(email)
                logger.debug("Restored email with UID %s to inbox.", email.uid)

            queryset.model.objects.filter(
                id__in=[email.id for email in emails_to_restore]
            ).delete()
            logger.debug("Deleted restored email messages from the database.")

        end_time = time.time()
        runtime = end_time - start_time
        messages.success(
            request,
            _(
                "Successfully restored {} emails to inbox and deleted "
                "them from trash in {:.2f} seconds."
            ).format(len(emails_to_restore), runtime),
        )

    except Exception as exc:
        end_time = time.time()
        runtime = end_time - start_time
        logger.error(
            "Error restoring email messages from trash: %s", str(exc), exc_info=True
        )
        messages.error(
            request,
            _(
                "Failed to restore and delete some emails from trash. "
                "Please try again. Task completed in {:.2f} seconds."
            ).format(runtime),
        )
        transaction.set_rollback(True)
