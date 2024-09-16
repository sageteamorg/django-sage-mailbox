from autoslug import AutoSlugField
from django.db import models
from django.utils.translation import gettext_lazy as _

from sage_mailbox.models.mixins import TimestampMixin
from sage_mailbox.utils import map_to_standard_name
from sage_mailbox.validators import validate_folder_name


def custom_slugify(value):
    return value.replace(".", "-").replace(" ", "-")


class StandardMailboxNames(models.TextChoices):
    INBOX = "INBOX", _("Inbox")
    SENT = "SENT", _("Sent")
    DRAFTS = "DRAFTS", _("Drafts")
    SPAM = "SPAM", _("Spam")
    JUNK = "JUNK", _("Junk")
    TRASH = "TRASH", _("Trash")
    CUSTOM = "CUSTOM", _("Custom")


IMAP_TO_STANDARD_MAP = {
    "INBOX": StandardMailboxNames.INBOX,
    "Sent Items": StandardMailboxNames.SENT,
    "Sent": StandardMailboxNames.SENT,
    "Drafts": StandardMailboxNames.DRAFTS,
    "Junk": StandardMailboxNames.JUNK,
    "Spam": StandardMailboxNames.SPAM,
    "Trash": StandardMailboxNames.TRASH,
    "Deleted Items": StandardMailboxNames.TRASH,
}


class Mailbox(TimestampMixin):
    name = models.CharField(
        max_length=255,
        unique=True,
        validators=[validate_folder_name],
        verbose_name=_("Name"),
        help_text=_("The unique name of the mailbox."),
        db_comment="The unique name identifying the mailbox.",
    )
    folder_type = models.CharField(
        max_length=255,
        verbose_name=_("Folder Type"),
        null=True,
        blank=False,
        help_text=_("The standardized type of the mailbox."),
        db_comment="The standardized type of the mailbox.",
        choices=StandardMailboxNames.choices,
        default=StandardMailboxNames.CUSTOM,
    )
    slug = AutoSlugField(
        verbose_name=_("Slug"),
        max_length=255,
        unique=True,
        always_update=True,
        allow_unicode=True,
        slugify=custom_slugify,
        populate_from="name",
        help_text=_("The unique slug for the mailbox, generated from the name."),
        db_comment="The unique slug generated from the mailbox name.",
    )

    class Meta:
        verbose_name = _("Mailbox")
        verbose_name_plural = _("Mailboxes")
        indexes = [
            models.Index(fields=["name"], name="idx_mailbox_name"),
            models.Index(fields=["slug"], name="idx_mailbox_slug"),
        ]
        db_table = "sage_mailbox"
        db_table_comment = (
            "Model representing a mailbox which can be nested under another mailbox."
        )

    def save(self, *args, **kwargs):
        # Map the name to the standard folder type
        if not self.pk:
            self.folder_type = map_to_standard_name(self.name)

        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.name)
