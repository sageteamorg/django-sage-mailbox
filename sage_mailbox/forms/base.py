"""
Base form classes for sage_mailbox.

This module contains base form classes that provide common functionality
for all forms in the sage_mailbox application.
"""

from django import forms
from django.forms import ModelForm


class BaseForm(forms.Form):
    """
    Base form class with common functionality for all forms.
    
    This class provides common configuration and methods that can be
    shared across all forms in the application.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add common CSS classes for styling
        self.add_css_classes()
    
    def add_css_classes(self):
        """Add common CSS classes to form fields."""
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.TextInput):
                field.widget.attrs.update({'class': 'form-control'})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'form-control'})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})


class BaseModelForm(ModelForm):
    """
    Base model form class with common functionality.
    
    This class provides common configuration and methods that can be
    shared across all model forms in the application.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add common CSS classes for styling
        self.add_css_classes()
    
    def add_css_classes(self):
        """Add common CSS classes to form fields."""
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.TextInput):
                field.widget.attrs.update({'class': 'form-control'})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'form-control'})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, forms.PasswordInput):
                field.widget.attrs.update({'class': 'form-control'}) 