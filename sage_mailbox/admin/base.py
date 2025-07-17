"""
Base admin classes for sage_mailbox.

This module contains the base admin configuration that provides common
functionality for all sage_mailbox admin classes.
"""

from django.contrib.admin import ModelAdmin


class BaseModelAdmin(ModelAdmin):
    """
    Base admin class with common configurations.
    
    This class provides standard configurations and behaviors that are
    shared across all sage_mailbox admin classes. It includes:
    - Common UI settings
    - Automatic readonly field management
    - Standard pagination settings
    """
    
    save_on_top = True
    list_per_page = 50
    
    def get_readonly_fields(self, request, obj=None):
        """Add created_at and updated_at to readonly fields."""
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if hasattr(self.model, 'created_at'):
            readonly_fields.append('created_at')
        if hasattr(self.model, 'updated_at'):
            readonly_fields.append('updated_at')
        return readonly_fields 