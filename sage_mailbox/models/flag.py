"""
Email flag model for sage_mailbox.

This module contains the EmailFlag model for storing custom email flags.
Flags are used to mark emails with custom labels or categories.
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _

from .mixins import TimestampMixin
from .email import Email


class EmailFlag(TimestampMixin):
    """
    Custom flag or label for email messages.
    
    This model allows users to create custom flags (labels) for organizing
    and categorizing emails beyond the standard IMAP flags. Custom flags
    can be used for project management, priority levels, or any other
    organizational system.
    
    Examples of custom flags:
    - Project names: "Project Alpha", "Client Work"
    - Priority levels: "Urgent", "Follow-up"
    - Categories: "Personal", "Work", "Newsletter"
    - Status indicators: "Needs Review", "Completed"
    
    Each flag belongs to a specific email and can have both a name
    and an optional value for additional information.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="Unique identifier for email flag"
    )
    
    email = models.ForeignKey(
        Email,
        on_delete=models.CASCADE,
        related_name="custom_flags",
        verbose_name=_("Email"),
        help_text=_("The email message that has this flag"),
        db_comment="Reference to the email with this flag"
    )
    
    flag_name = models.CharField(
        max_length=100,
        verbose_name=_("Flag name"),
        help_text=_("The name of the custom flag (e.g., 'Important', 'Project Alpha')"),
        db_comment="Name of the custom flag"
    )
    
    flag_value = models.TextField(
        blank=True,
        verbose_name=_("Flag value"),
        help_text=_("Optional additional information for this flag"),
        db_comment="Value of the custom flag"
    )
    
    class Meta:
        db_table = "sage_email_flag"
        verbose_name = _("Email Flag")
        verbose_name_plural = _("Email Flags")
        unique_together = ["email", "flag_name"]
        ordering = ["flag_name"]
    
    def __str__(self):
        return f"{self.flag_name}: {self.flag_value}" 