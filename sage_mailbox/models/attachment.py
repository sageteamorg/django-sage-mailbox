import mimetypes

from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils.translation import gettext_lazy as _

from sage_mailbox.models.mixins import TimestampMixin


class Attachment(TimestampMixin):
    email_message = models.ForeignKey(
        "EmailMessage",
        related_name="attachments",
        on_delete=models.CASCADE,
        verbose_name=_("Email Message"),
        help_text=_("The email message to which this attachment belongs."),
        db_comment="The email message to which this attachment belongs.",
    )
    attachment_id = models.CharField(max_length=255, blank=True, null=True)
    file = models.FileField(
        upload_to="attachments/%Y/%m/%d/",
        storage=FileSystemStorage("sage_mailbox/attachments/"),
        verbose_name=_("File"),
        help_text=_("The file attached to the email."),
        db_comment="The file attached to the email.",
    )
    filename = models.CharField(
        max_length=255,
        verbose_name=_("Filename"),
        help_text=_("The original filename of the attachment."),
        db_comment="The original filename of the attachment.",
    )
    content_type = models.CharField(
        max_length=255,
        verbose_name=_("Content Type"),
        help_text=_("The MIME type of the attachment."),
        db_comment="The MIME type of the attachment.",
    )
    payload = models.BinaryField()
    content_id = models.CharField(max_length=255, blank=True, null=True)
    content_transfer_encoding = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = _("Attachment")
        verbose_name_plural = _("Attachments")
        indexes = [
            models.Index(fields=["filename"], name="idx_attachment_filename"),
        ]
        db_table = "sage_attachment"
        db_table_comment = "Model representing an attachment to an email message."

    # pylint: disable= C0103
    def save(self, *args, **kwargs):
        if not self.content_type and self.file:
            self.content_type, _ = mimetypes.guess_type(self.file.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.filename) or "Attachment"
