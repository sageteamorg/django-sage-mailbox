"""
Model mixins for sage_mailbox.

This module contains reusable model mixins that provide common functionality.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class TimestampMixin(models.Model):
    """
    Abstract base model that provides automatic timestamp fields.
    
    This mixin adds created_at and updated_at fields to any model that inherits from it.
    The created_at field is automatically set when a record is first saved,
    and updated_at is automatically updated every time the record is saved.
    
    Use this mixin for any model that needs to track when records were created
    and last modified.
    """
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created at"),
        help_text=_("When this record was first created. This is set automatically and cannot be changed."),
        db_comment="Timestamp when record was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated at"),
        help_text=_("When this record was last modified. This is updated automatically every time you save changes."),
        db_comment="Timestamp when record was last updated"
    )
    
    class Meta:
        abstract = True 