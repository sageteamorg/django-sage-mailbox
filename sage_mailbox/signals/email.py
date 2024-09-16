import email
import logging
import mimetypes
from email.utils import make_msgid

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.timezone import now
from sage_imap.services import IMAPClient, IMAPMailboxService

from sage_mailbox.models import EmailMessage, Sent
from sage_mailbox.models.mailbox import Mailbox, StandardMailboxNames

logger = logging.getLogger(__name__)

# pylint: disable=W0613, C0103


@receiver(post_save, sender=EmailMessage)
def send_email_after_save(sender, instance, created, **kwargs):
    if created:
        transaction.on_commit(lambda: send_email(instance))


def send_email(email_message):
    current_site = Site.objects.get_current()
    # Generate a Message-ID if not present
    if not email_message.message_id:
        email_message.message_id = make_msgid(domain=current_site.domain)

    # Ensure the date is set
    if not email_message.date:
        email_message.date = now()

    # Create the email message
    subject = email_message.subject
    from_email = email_message.from_address
    to = email_message.to_address.split(",")
    cc = email_message.cc_address.split(",") if email_message.cc_address else []
    bcc = email_message.bcc_address.split(",") if email_message.bcc_address else []

    msg = EmailMultiAlternatives(
        subject=subject,
        body=email_message.plain_body,
        from_email=from_email,
        to=to,
        cc=cc,
        bcc=bcc,
    )

    # Check if the body contains HTML content
    if email_message.html_body:
        msg.attach_alternative(email_message.html_body, "text/html")

    # Attach any files
    for attachment in email_message.attachments.all():
        file_content = attachment.file.read()
        mime_type, _ = mimetypes.guess_type(attachment.filename)
        if not mime_type:
            # Default to binary stream if MIME type can't be guessed
            mime_type = "application/octet-stream"
        msg.attach(attachment.filename, file_content, mime_type)

    # Additional headers
    msg.extra_headers = {
        "Message-ID": email_message.message_id,
        "X-MS-Has-Attach": "yes" if email_message.has_attachments() else "no",
        "X-Priority": "3",
        "X-Auto-Response-Suppress": "All",
        "MIME-Version": "1.0",
        "Content-Type": "multipart/mixed",
    }

    # Send the email
    msg.send()

    # Save raw email to IMAP Sent folder and get raw email data
    raw_email = msg.message().as_string()
    email_message.raw = raw_email.encode("utf-8")  # Ensure raw email is bytes

    host = settings.IMAP_SERVER_DOMAIN
    username = settings.IMAP_SERVER_USER
    password = settings.IMAP_SERVER_PASSWORD

    with IMAPClient(host, username, password) as client:
        with IMAPMailboxService(client) as mailbox:
            folder = Mailbox.objects.get(folder_type=StandardMailboxNames.SENT)
            mailbox.select(folder.name)
            mailbox.save_sent(email_message.raw, folder.name)  # Send raw email as bytes

    # Save headers to email_message
    parsed_email = email.message_from_bytes(email_message.raw)
    headers = {k: v for k, v in parsed_email.items()}
    email_message.headers = headers

    # Calculate and save email size
    email_message.size = len(email_message.raw)

    # Save email message with updated fields
    email_message.save()


# Connect the signal to all proxies
proxy_models = [EmailMessage, Sent]

for model in proxy_models:
    post_save.connect(send_email_after_save, sender=model)
