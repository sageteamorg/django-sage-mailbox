import time
import logging
import zipfile
from io import BytesIO

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _

from sage_imap.models.message import MessageSet
from sage_imap.helpers.enums import Flag, FlagCommand
from sage_imap.services import IMAPClient, IMAPMailboxUIDService
from sage_mailbox.models.mailbox import Mailbox, StandardMailboxNames


logger = logging.getLogger(__name__)

host = settings.IMAP_SERVER_DOMAIN
username = settings.IMAP_SERVER_USER
password = settings.IMAP_SERVER_PASSWORD

@admin.action(description=_('Move selected emails to trash'))
@transaction.atomic
def move_to_trash(modeladmin, request, queryset):
    start_time = time.time()
    email_messages_to_update = []
    try:
        with IMAPClient(host, username, password) as client:
            mailbox = IMAPMailboxUIDService(client)
            trash_mailbox = Mailbox.objects.get(
                folder_type=StandardMailboxNames.TRASH
            )

            for email_message in queryset:
                mailbox.select(email_message.mailbox.name)
                mailbox.uid_trash(MessageSet(str(email_message.uid)), trash_mailbox.name)
                email_message.mailbox = trash_mailbox
                email_messages_to_update.append(email_message)
                logger.debug(f"Moved email with UID {email_message.uid} to trash.")

            queryset.model.objects.bulk_update(email_messages_to_update, ['mailbox'])
            logger.debug("Moved email messages to trash in the database.")

        end_time = time.time()
        runtime = end_time - start_time
        messages.success(request, _("Successfully moved {} emails to trash in {:.2f} seconds.").format(len(email_messages_to_update), runtime))

    except Exception as e:
        end_time = time.time()
        runtime = end_time - start_time
        logger.error(f"Error moving email messages to trash: {str(e)}", exc_info=True)
        messages.error(request, _("Failed to move some emails to trash. Please try again. Task completed in {:.2f} seconds.").format(runtime))
        transaction.set_rollback(True)


@admin.action(description=_('Mark selected emails as read'))
@transaction.atomic
def mark_as_read(modeladmin, request, queryset):
    start_time = time.time()
    email_messages_to_update = []
    try:
        with IMAPClient(host, username, password) as client:
            mailbox = IMAPMailboxUIDService(client)

            for email_message in queryset:
                mailbox.select(email_message.mailbox.name)
                if not email_message.is_read:
                    status, data = client.uid('STORE', str(email_message.uid), '+FLAGS', '\\Seen')
                    logger.debug(f"Marked email with UID {email_message.uid} as SEEN.")

                    email_message.is_read = True
                    email_messages_to_update.append(email_message)
                    logger.debug(f"Prepared to mark email message object {email_message.pk} as read in the database.")

        # Bulk update all email messages at once
        queryset.model.objects.bulk_update(email_messages_to_update, ['is_read'])
        logger.debug("Bulk updated all email messages to read status in the database.")
        
        end_time = time.time()
        runtime = end_time - start_time
        messages.success(request, _("Successfully marked {} emails as read in {:.2f} seconds.").format(len(email_messages_to_update), runtime))

    except Exception as e:
        end_time = time.time()
        runtime = end_time - start_time
        logger.error(f"Error marking email messages as read: {str(e)}", exc_info=True)
        messages.error(request, _("Failed to mark some emails as read. Please try again. Task completed in {:.2f} seconds.").format(runtime))
        transaction.set_rollback(True)


@admin.action(description=_('Mark selected emails as unread'))
@transaction.atomic
def mark_as_unread(modeladmin, request, queryset):
    start_time = time.time()
    email_messages_to_update = []
    try:

        with IMAPClient(host, username, password) as client:
            mailbox = IMAPMailboxUIDService(client)

            for email_message in queryset:
                mailbox.select(email_message.mailbox.name)
                if email_message.is_read:
                    # TODO: python-sage-imap does not support uid on flag service
                    status, data = client.uid('STORE', str(email_message.uid), FlagCommand.REMOVE, Flag.SEEN)
                    logger.debug(f"Unmarked email with Message-ID {email_message.uid} as SEEN.")

                    email_message.is_read = False
                    email_messages_to_update.append(email_message)
                    logger.debug(f"Prepared to mark email message object {email_message.pk} as unread in the database.")

        # Bulk update all email messages at once
        queryset.model.objects.bulk_update(email_messages_to_update, ['is_read'])
        logger.debug("Bulk updated all email messages to unread status in the database.")
        
        end_time = time.time()
        runtime = end_time - start_time
        messages.success(request, _("Successfully marked {} emails as unread in {:.2f} seconds.").format(len(email_messages_to_update), runtime))

    except Exception as e:
        end_time = time.time()
        runtime = end_time - start_time
        logger.error(f"Error marking email messages as unread: {str(e)}", exc_info=True)
        messages.error(request, _("Failed to mark some emails as unread. Please try again. Task completed in {:.2f} seconds.").format(runtime))
        transaction.set_rollback(True)

@admin.action(description=_('Mark selected emails as flagged'))
@transaction.atomic
def mark_as_flagged(modeladmin, request, queryset):
    start_time = time.time()
    email_messages_to_update = []
    try:
        with IMAPClient(host, username, password) as client:
            mailbox = IMAPMailboxUIDService(client)

            for email_message in queryset:
                mailbox.select(email_message.mailbox.name)
                if not email_message.is_flagged:
                    status, data = client.uid('STORE', str(email_message.uid), '+FLAGS', '\\Flagged')
                    logger.debug(f"Marked email with UID {email_message.uid} as FLAGGED.")

                    email_message.is_flagged = True
                    email_messages_to_update.append(email_message)
                    logger.debug(f"Prepared to mark email message object {email_message.pk} as flagged in the database.")

        # Bulk update all email messages at once
        queryset.model.objects.bulk_update(email_messages_to_update, ['is_flagged'])
        logger.debug("Bulk updated all email messages to flagged status in the database.")
        
        end_time = time.time()
        runtime = end_time - start_time
        messages.success(request, _("Successfully marked {} emails as flagged in {:.2f} seconds.").format(len(email_messages_to_update), runtime))

    except Exception as e:
        end_time = time.time()
        runtime = end_time - start_time
        logger.error(f"Error marking email messages as flagged: {str(e)}", exc_info=True)
        messages.error(request, _("Failed to mark some emails as flagged. Please try again. Task completed in {:.2f} seconds.").format(runtime))
        transaction.set_rollback(True)


@admin.action(description=_('Mark selected emails as unflagged'))
@transaction.atomic
def mark_as_unflagged(modeladmin, request, queryset):
    start_time = time.time()
    email_messages_to_update = []
    try:

        with IMAPClient(host, username, password) as client:
            mailbox = IMAPMailboxUIDService(client)

            for email_message in queryset:
                mailbox.select(email_message.mailbox.name)
                if email_message.is_flagged:
                    status, data = client.uid('STORE', str(email_message.uid), '-FLAGS', '\\Flagged')
                    logger.debug(f"Unmarked email with UID {email_message.uid} as FLAGGED.")

                    email_message.is_flagged = False
                    email_messages_to_update.append(email_message)
                    logger.debug(f"Prepared to mark email message object {email_message.pk} as unflagged in the database.")

        # Bulk update all email messages at once
        queryset.model.objects.bulk_update(email_messages_to_update, ['is_flagged'])
        logger.debug("Bulk updated all email messages to unflagged status in the database.")
        
        end_time = time.time()
        runtime = end_time - start_time
        messages.success(request, _("Successfully marked {} emails as unflagged in {:.2f} seconds.").format(len(email_messages_to_update), runtime))

    except Exception as e:
        end_time = time.time()
        runtime = end_time - start_time
        logger.error(f"Error marking email messages as unflagged: {str(e)}", exc_info=True)
        messages.error(request, _("Failed to mark some emails as unflagged. Please try again. Task completed in {:.2f} seconds.").format(runtime))
        transaction.set_rollback(True)

@admin.action(description=_('Download selected emails as EML'))
def download_as_eml(modeladmin, request, queryset):
    start_time = time.time()
    email_files = []

    try:
        for email_message in queryset:
            if email_message.raw:
                email_files.append((f"{email_message.uid}.eml", email_message.raw))
                logger.debug(f"Added raw data for email with Message-ID {email_message.uid}.")

        if len(email_files) == 1:
            response = HttpResponse(email_files[0][1], content_type='message/rfc822')
            response['Content-Disposition'] = f'attachment; filename="{email_files[0][0]}"'
            logger.debug(f"Prepared single EML file for download: {email_files[0][0]}")
        else:
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                for file_name, eml_data in email_files:
                    zip_file.writestr(file_name, eml_data)
                    logger.debug(f"Added {file_name} to zip file.")

            zip_buffer.seek(0)
            response = HttpResponse(zip_buffer, content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="emails.zip"'
            logger.debug("Prepared zip file for download containing multiple EML files.")

        end_time = time.time()
        runtime = end_time - start_time
        messages.success(request, _("Successfully prepared download for {} emails in {:.2f} seconds.").format(len(email_files), runtime))
        return response

    except Exception as e:
        logger.error(f"An error occurred while preparing the EML files: {str(e)}")
        messages.error(request, _("An error occurred while preparing the EML files."))
        return None


@admin.action(description=_('Restore selected emails from trash to inbox'))
@transaction.atomic
def restore_from_trash(modeladmin, request, queryset):
    start_time = time.time()
    email_messages_to_update = []
    try:

        with IMAPClient(host, username, password) as client:
            mailbox_service = IMAPMailboxUIDService(client)
            trash_mailbox = Mailbox.objects.get(folder_type=StandardMailboxNames.TRASH)
            inbox_mailbox = Mailbox.objects.get(folder_type=StandardMailboxNames.INBOX)

            for email_message in queryset:
                mailbox_service.select(trash_mailbox.name)
                mailbox_service.uid_restore(
                    MessageSet(str(email_message.uid)),
                    trash_mailbox,
                    inbox_mailbox
                )
                email_message.mailbox = inbox_mailbox
                email_messages_to_update.append(email_message)
                logger.debug(f"Restored email with UID {email_message.uid} to inbox.")

            queryset.model.objects.bulk_update(email_messages_to_update, ['mailbox'])
            logger.debug("Restored email messages to inbox in the database.")

        end_time = time.time()
        runtime = end_time - start_time
        messages.success(request, _("Successfully restored {} emails from trash to inbox in {:.2f} seconds.").format(len(email_messages_to_update), runtime))

    except Exception as e:
        end_time = time.time()
        runtime = end_time - start_time
        logger.error(f"Error restoring email messages from trash: {str(e)}", exc_info=True)
        messages.error(request, _("Failed to restore some emails from trash. Please try again. Task completed in {:.2f} seconds.").format(runtime))
        transaction.set_rollback(True)
