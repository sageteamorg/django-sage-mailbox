import logging
import mimetypes

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from sage_imap.helpers.mailbox import DefaultMailboxes
from sage_imap.services import IMAPClient, IMAPMailboxService

from sage_mailbox.models import Archive, Draft, EmailMessage, Inbox, Junk, Sent, Trash

logger = logging.getLogger(__name__)


@receiver(post_save, sender=EmailMessage)
def send_email_after_save(sender, instance, created, **kwargs):
    if created:
        transaction.on_commit(lambda: send_email(instance))

def send_email(email_message):
    # Create the email message
    subject = email_message.subject
    from_email = email_message.from_address
    to = email_message.to_address.split(',')
    cc = email_message.cc_address.split(',') if email_message.cc_address else []
    bcc = email_message.bcc_address.split(',') if email_message.bcc_address else []

    msg = EmailMultiAlternatives(
        subject=subject,
        body=email_message.body,
        from_email=from_email,
        to=to,
        cc=cc,
        bcc=bcc,
    )

    # Check if the body contains HTML content
    if '<html>' in email_message.body:
        msg.attach_alternative(email_message.body, "text/html")

    # Attach any files
    for attachment in email_message.attachments.all():
        file_content = attachment.file.read()
        mime_type, _ = mimetypes.guess_type(attachment.filename)
        if not mime_type:
            mime_type = 'application/octet-stream'  # Default to binary stream if MIME type can't be guessed
        msg.attach(attachment.filename, file_content, mime_type)

    # Additional headers
    msg.extra_headers = {
        'Message-ID': email_message.message_id,
        'X-MS-Has-Attach': 'yes' if email_message.has_attachments() else 'no',
        'X-Priority': '3',
        'X-Auto-Response-Suppress': 'All',
        'MIME-Version': '1.0',
        'Content-Type': 'multipart/mixed',
    }

    # Send the email
    msg.send()

    # Save email to IMAP Sent folder
    raw_email = msg.message().as_string()
    host = settings.IMAP_SERVER_DOMAIN
    username = settings.IMAP_SERVER_USER
    password = settings.IMAP_SERVER_PASSWORD

    with IMAPClient(host, username, password) as client:
        with IMAPMailboxService(client) as mailbox:
            mailbox.save_sent_email(raw_email, DefaultMailboxes.SENT)

# Connect the signal to all proxies
proxy_models = [EmailMessage, Inbox, Draft, Sent, Trash, Junk, Archive]

for model in proxy_models:
    post_save.connect(send_email_after_save, sender=model)
