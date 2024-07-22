from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from sage_mailbox.models.mixins import TimestampMixin
from sage_mailbox.validators import validate_folder_name
from sage_mailbox.utils import map_to_standard_name



class StandardMailboxNames(models.TextChoices):
    INBOX = 'INBOX', _('Inbox')
    SENT = 'SENT', _('Sent')
    DRAFTS = 'DRAFTS', _('Drafts')
    SPAM = 'SPAM', _('Spam')
    TRASH = 'TRASH', _('Trash')
    CUSTOM = "CUSTOM", _("Custom")


IMAP_TO_STANDARD_MAP = {
    'INBOX': StandardMailboxNames.INBOX,
    'Sent Items': StandardMailboxNames.SENT,
    'Sent': StandardMailboxNames.SENT,
    'Drafts': StandardMailboxNames.DRAFTS,
    'Junk': StandardMailboxNames.SPAM,
    'Spam': StandardMailboxNames.SPAM,
    'Trash': StandardMailboxNames.TRASH,
    'Deleted Items': StandardMailboxNames.TRASH,
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
        default=StandardMailboxNames.CUSTOM
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        allow_unicode=True,
        verbose_name=_("Slug"),
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
        # Generate slug if not provided or if it's not unique
        if not self.slug or Mailbox.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
            self.slug = self.generate_unique_slug()

        # Map the name to the standard folder type
        self.folder_type = map_to_standard_name(self.name)
        
        super(Mailbox, self).save(*args, **kwargs)

    def generate_unique_slug(self):
        original_slug = slugify(self.name.lower())
        unique_slug = original_slug
        num = 1

        while Mailbox.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
            unique_slug = f"{original_slug}-{num}"
            num += 1

        return unique_slug

    def __str__(self):
        return self.name
