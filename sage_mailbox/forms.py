from django import forms
from django.utils.translation import gettext_lazy as _
from .models import SMTPServer, EmailTemplate


class EmailComposeForm(forms.Form):
    """Form for composing emails."""
    
    smtp_server = forms.ModelChoiceField(
        queryset=SMTPServer.objects.none(),
        empty_label=_('Select SMTP Server'),
        label=_('SMTP Server'),
        required=True
    )
    
    template = forms.ModelChoiceField(
        queryset=EmailTemplate.objects.none(),
        empty_label=_('No Template'),
        label=_('Email Template'),
        required=False,
        help_text=_('Optional template to use')
    )
    
    to_addresses = forms.CharField(
        label=_('To'),
        max_length=1000,
        help_text=_('Comma-separated email addresses'),
        widget=forms.TextInput(attrs={'placeholder': 'recipient@example.com, another@example.com'})
    )
    
    cc_addresses = forms.CharField(
        label=_('CC'),
        max_length=1000,
        required=False,
        help_text=_('Comma-separated email addresses'),
        widget=forms.TextInput(attrs={'placeholder': 'cc@example.com, another@example.com'})
    )
    
    bcc_addresses = forms.CharField(
        label=_('BCC'),
        max_length=1000,
        required=False,
        help_text=_('Comma-separated email addresses'),
        widget=forms.TextInput(attrs={'placeholder': 'bcc@example.com, another@example.com'})
    )
    
    subject = forms.CharField(
        label=_('Subject'),
        max_length=255,
        required=True
    )
    
    priority = forms.ChoiceField(
        label=_('Priority'),
        choices=[
            ('normal', _('Normal')),
            ('high', _('High')),
            ('low', _('Low'))
        ],
        initial='normal',
        required=False
    )
    
    body_html = forms.CharField(
        label=_('HTML Body'),
        widget=forms.Textarea(attrs={'rows': 15, 'cols': 80, 'placeholder': 'Enter HTML content here...'}),
        required=False,
        help_text=_('Rich HTML content for the email')
    )
    
    body_plain = forms.CharField(
        label=_('Plain Text Body'),
        widget=forms.Textarea(attrs={'rows': 10, 'cols': 80, 'placeholder': 'Enter plain text content here...'}),
        required=False,
        help_text=_('Plain text version (auto-synced from HTML)')
    )
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter querysets based on user
        self.fields['smtp_server'].queryset = SMTPServer.objects.filter(owner=user, is_active=True)
        self.fields['template'].queryset = EmailTemplate.objects.filter(owner=user, is_active=True)
        
        # Add template data attributes
        template_choices = []
        for template in self.fields['template'].queryset:
            template_choices.append((template.id, template.name))
        
        # Add data attributes for JavaScript
        template_options = []
        for template in self.fields['template'].queryset:
            template_options.append((template.id, template.name))
        
        # Create custom widget with data attributes
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
            return addr_list
        raise forms.ValidationError(_('At least one recipient is required'))
    
    def clean_cc_addresses(self):
        """Validate and clean CC addresses."""
        addresses = self.cleaned_data.get('cc_addresses', '')
        if addresses:
            return [addr.strip() for addr in addresses.split(',') if addr.strip()]
        return []
    
    def clean_bcc_addresses(self):
        """Validate and clean BCC addresses."""
        addresses = self.cleaned_data.get('bcc_addresses', '')
        if addresses:
            return [addr.strip() for addr in addresses.split(',') if addr.strip()]
        return [] 