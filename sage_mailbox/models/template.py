"""
Email template model for sage_mailbox.

This module contains the EmailTemplate model for storing reusable email templates.
Templates allow users to create standardized email formats for common messages.
"""

import uuid
from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

from .mixins import TimestampMixin


class EmailTemplate(TimestampMixin):
    """
    Reusable email template for standardized messaging.
    
    This model allows users to create and store email templates that can be
    reused for common messages. Templates can include both HTML and plain text
    versions of the email content.
    
    Templates are useful for:
    - Welcome emails
    - Support responses
    - Marketing messages
    - Automated notifications
    
    Each template belongs to a specific user and can be activated/deactivated
    as needed.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="Unique identifier for email template"
    )
    
    name = models.CharField(
        max_length=100,
        verbose_name=_("Template name"),
        help_text=_("Give this template a descriptive name (e.g., 'Welcome Email', 'Support Reply')"),
        db_comment="Name of the email template"
    )
    
    subject = models.CharField(
        max_length=255,
        verbose_name=_("Subject"),
        help_text=_("The subject line that will appear in emails created from this template"),
        db_comment="Email subject template"
    )
    
    body_html = models.TextField(
        blank=True,
        verbose_name=_("HTML body"),
        help_text=_("The rich HTML content of the email (with formatting, images, etc.)"),
        db_comment="HTML body of the email template"
    )
    
    body_plain = models.TextField(
        blank=True,
        verbose_name=_("Plain text body"),
        help_text=_("The plain text version of the email (without formatting, for basic email clients)"),
        db_comment="Plain text body of the email template"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
        help_text=_("Uncheck to temporarily disable this template without deleting it"),
        db_comment="Whether template is active"
    )
    
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="email_templates",
        verbose_name=_("Owner"),
        help_text=_("The user account that owns this email template"),
        db_comment="User who owns this template"
    )
    
    class Meta:
        db_table = "sage_email_template"
        verbose_name = _("Email Template")
        verbose_name_plural = _("Email Templates")
        ordering = ["name"]
        unique_together = ["name", "owner"]
    
    def __str__(self):
        return f"{self.name} ({self.owner.username})" 