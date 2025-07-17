"""
Email forms for sage_mailbox.

This module contains forms for email management including
email composition, editing, and validation.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.forms import Textarea
from django.utils.translation import gettext_lazy as _

from ..models import Email, EmailTemplate, SMTPServer
from .base import BaseModelForm, BaseForm


class EmailForm(BaseModelForm):
    """
    Custom form for Email model.
    
    This form provides proper widgets and validation for email fields,
    including proper textarea sizing for email content.
    """
    
    class Meta:
        model = Email
        fields = '__all__'
        widgets = {
            'headers': Textarea(attrs={'rows': 10}),
            'plain_body': Textarea(attrs={'rows': 15}),
            'html_body': Textarea(attrs={'rows': 15}),
        }
        help_text = {
            'subject': _('Email subject line'),
            'from_address': _('Sender email address'),
            'from_name': _('Sender display name'),
            'to_addresses': _('Recipient email addresses'),
            'cc_addresses': _('Carbon copy recipients'),
            'bcc_addresses': _('Blind carbon copy recipients'),
            'reply_to': _('Reply-to email address'),
            'plain_body': _('Plain text version of the email'),
            'html_body': _('HTML version of the email'),
            'priority': _('Email priority level'),
        }


class EmailComposeForm(BaseForm):
    """
    Form for composing and sending emails.
    
    This form provides all the necessary fields for composing emails
    with template support and proper validation.
    """
    
    smtp_server = forms.ModelChoiceField(
        queryset=SMTPServer.objects.none(),
        empty_label=_('Select SMTP Server'),
        label=_('SMTP Server'),
        required=True,
        help_text=_('Choose the SMTP server to send this email through')
    )
    
    template = forms.ModelChoiceField(
        queryset=EmailTemplate.objects.none(),
        empty_label=_('No Template'),
        label=_('Email Template'),
        required=False,
        help_text=_('Optional template to use as a starting point')
    )
    
    to_addresses = forms.CharField(
        label=_('To'),
        max_length=1000,
        help_text=_('Email addresses separated by commas (e.g., user1@example.com, user2@example.com)'),
        widget=forms.TextInput(attrs={
            'placeholder': 'recipient@example.com, another@example.com',
            'size': 60
        })
    )
    
    cc_addresses = forms.CharField(
        label=_('CC'),
        max_length=1000,
        required=False,
        help_text=_('Carbon copy recipients - they will see who else received the email'),
        widget=forms.TextInput(attrs={
            'placeholder': 'cc@example.com, another@example.com',
            'size': 60
        })
    )
    
    bcc_addresses = forms.CharField(
        label=_('BCC'),
        max_length=1000,
        required=False,
        help_text=_('Blind carbon copy recipients - they will not see other recipients'),
        widget=forms.TextInput(attrs={
            'placeholder': 'bcc@example.com, another@example.com',
            'size': 60
        })
    )
    
    subject = forms.CharField(
        label=_('Subject'),
        max_length=255,
        required=True,
        help_text=_('The subject line of your email'),
        widget=forms.TextInput(attrs={'size': 60})
    )
    
    priority = forms.ChoiceField(
        label=_('Priority'),
        choices=[
            ('normal', _('Normal')),
            ('high', _('High')),
            ('low', _('Low'))
        ],
        initial='normal',
        required=False,
        help_text=_('Email priority level')
    )
    
    body_html = forms.CharField(
        label=_('HTML Body'),
        widget=forms.Textarea(attrs={
            'rows': 15, 
            'cols': 80, 
            'placeholder': 'Enter HTML content here...'
        }),
        required=False,
        help_text=_('Rich HTML content for the email (supports formatting, links, images)')
    )
    
    body_plain = forms.CharField(
        label=_('Plain Text Body'),
        widget=forms.Textarea(attrs={
            'rows': 10, 
            'cols': 80, 
            'placeholder': 'Enter plain text content here...'
        }),
        required=False,
        help_text=_('Plain text version of the email (automatically generated from HTML if not provided)')
    )
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter querysets based on user
        self.fields['smtp_server'].queryset = SMTPServer.objects.filter(owner=user, is_active=True)
        self.fields['template'].queryset = EmailTemplate.objects.filter(owner=user, is_active=True)
        
        # Create custom widget with data attributes for templates
        from django.forms.widgets import Select
        
        class TemplateSelect(Select):
            def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
                option = super().create_option(name, value, label, selected, index, subindex, attrs)
                if value:
                    try:
                        template = EmailTemplate.objects.get(id=value)
                        option['attrs'][f'data-template-{template.id}-subject'] = template.subject
                        option['attrs'][f'data-template-{template.id}-html'] = template.body_html
                        option['attrs'][f'data-template-{template.id}-plain'] = template.body_plain
                    except EmailTemplate.DoesNotExist:
                        pass
                return option
        
        self.fields['template'].widget = TemplateSelect()
    
    def clean_to_addresses(self):
        """Validate and clean to addresses."""
        addresses = self.cleaned_data.get('to_addresses', '')
        if addresses:
            # Split by comma and strip whitespace
            addr_list = [addr.strip() for addr in addresses.split(',') if addr.strip()]
            if not addr_list:
                raise forms.ValidationError(_('At least one recipient is required'))
            
            # Validate each email address
            from django.core.validators import validate_email
            for addr in addr_list:
                try:
                    validate_email(addr)
                except ValidationError:
                    raise forms.ValidationError(_('Invalid email address: %(email)s'), params={'email': addr})
            
            return addr_list
        raise forms.ValidationError(_('At least one recipient is required'))
    
    def clean_cc_addresses(self):
        """Validate and clean CC addresses."""
        addresses = self.cleaned_data.get('cc_addresses', '')
        if addresses:
            addr_list = [addr.strip() for addr in addresses.split(',') if addr.strip()]
            
            # Validate each email address
            from django.core.validators import validate_email
            for addr in addr_list:
                try:
                    validate_email(addr)
                except ValidationError:
                    raise forms.ValidationError(_('Invalid CC email address: %(email)s'), params={'email': addr})
            
            return addr_list
        return []
    
    def clean_bcc_addresses(self):
        """Validate and clean BCC addresses."""
        addresses = self.cleaned_data.get('bcc_addresses', '')
        if addresses:
            addr_list = [addr.strip() for addr in addresses.split(',') if addr.strip()]
            
            # Validate each email address
            from django.core.validators import validate_email
            for addr in addr_list:
                try:
                    validate_email(addr)
                except ValidationError:
                    raise forms.ValidationError(_('Invalid BCC email address: %(email)s'), params={'email': addr})
            
            return addr_list
        return []
    
    def clean(self):
        """Validate that at least one body type is provided."""
        cleaned_data = super().clean()
        body_html = cleaned_data.get('body_html')
        body_plain = cleaned_data.get('body_plain')
        
        if not body_html and not body_plain:
            raise forms.ValidationError(_('Please provide either HTML body or plain text body (or both)'))
        
        return cleaned_data 