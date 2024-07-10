from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from sage_mailbox.models.mixins import TimestampMixin


class Mailbox(TimestampMixin):
    name = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_("Name"),
        help_text=_("The unique name of the mailbox."),
        db_comment="The unique name identifying the mailbox.",
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
        if not self.slug:
            self.slug = slugify(self.name)
        super(Mailbox, self).save(*args, **kwargs)

    def __str__(self):
        return self.name
