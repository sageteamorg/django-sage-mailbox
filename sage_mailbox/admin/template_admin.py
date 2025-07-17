"""
Django admin configuration for email template models.

This module provides admin interfaces for managing email templates
with rich text editing capabilities.
"""

from django.contrib import admin
from django.contrib import messages
from django.forms import Textarea
from django.utils.translation import gettext_lazy as _

from ..models import EmailTemplate
from .base import BaseModelAdmin


@admin.register(EmailTemplate)
class EmailTemplateAdmin(BaseModelAdmin):
    """Admin interface for Email Template model."""
    
    list_display = [
        'name', 'subject', 'owner', 'is_active', 'created_at', 'updated_at'
    ]
    list_display_links = ['name', 'subject']
    list_filter = ['is_active', 'created_at', 'owner']
    search_fields = ['name', 'subject', 'body_html', 'body_plain', 'owner__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'owner', 'is_active')
        }),
        (_('Email Content'), {
            'fields': ('subject', 'body_html', 'body_plain'),
            'description': 'Configure the email template content'
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_templates', 'deactivate_templates', 'duplicate_templates']
    
    def get_form(self, request, obj=None, **kwargs):
        """Customize form for rich text editing."""
        form = super().get_form(request, obj, **kwargs)
        
        # Add rich text editor for HTML body
        form.base_fields['body_html'].widget = Textarea(attrs={
            'rows': 20,
            'cols': 100,
            'class': 'vLargeTextField',
            'style': 'font-family: monospace;'
        })
        
        form.base_fields['body_plain'].widget = Textarea(attrs={
            'rows': 15,
            'cols': 100,
            'class': 'vLargeTextField'
        })
        
        return form
    
    def activate_templates(self, request, queryset):
        """Activate selected templates."""
        updated = queryset.update(is_active=True)
        messages.success(request, f"Activated {updated} template(s)")
    
    activate_templates.short_description = _('Activate templates')
    
    def deactivate_templates(self, request, queryset):
        """Deactivate selected templates."""
        updated = queryset.update(is_active=False)
        messages.success(request, f"Deactivated {updated} template(s)")
    
    deactivate_templates.short_description = _('Deactivate templates')
    
    def duplicate_templates(self, request, queryset):
        """Duplicate selected templates."""
        duplicated_count = 0
        for template in queryset:
            template.pk = None
            template.name = f"{template.name} (Copy)"
            template.save()
            duplicated_count += 1
        
        messages.success(request, f"Duplicated {duplicated_count} template(s)")
    
    duplicate_templates.short_description = _('Duplicate templates') 