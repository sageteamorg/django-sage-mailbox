"""
Utility functions for sage_mailbox application.

This module provides conversion utilities between sage_imap dataclasses and Django models,
along with other helper functions for email processing, security, and data manipulation.
"""

import hashlib
import logging
import mimetypes
import os
import zipfile
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple, Union

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from django.utils.text import slugify
from django.conf import settings

from sage_imap.helpers.enums import Flag, DefaultMailboxes
from sage_imap.models.email import EmailMessage as SageEmailMessage
from sage_imap.models.email import Attachment as SageAttachment
from sage_imap.helpers.typings import EmailAddress, EmailDate

logger = logging.getLogger(__name__)


class EmailConverter:
    """Handles conversion between sage_imap and Django models."""
    
    @staticmethod
    def sage_to_django_email(sage_email: SageEmailMessage, mailbox, uid: int) -> Dict[str, Any]:
        """
        Convert sage_imap EmailMessage to Django Email field dictionary.
        
        Args:
            sage_email: SageEmailMessage instance
            mailbox: Django Mailbox instance
            uid: Email UID
            
        Returns:
            Dictionary with Django Email field values
        """
        # Parse addresses
        to_addresses = [str(addr) for addr in sage_email.to_address] if sage_email.to_address else []
        cc_addresses = [str(addr) for addr in sage_email.cc_address] if sage_email.cc_address else []
        bcc_addresses = [str(addr) for addr in sage_email.bcc_address] if sage_email.bcc_address else []
        
        # Parse from address
        from_address = str(sage_email.from_address) if sage_email.from_address else ""
        from_name = ""
        
        # Extract display name from from_address if available
        if sage_email.from_address and hasattr(sage_email.from_address, 'display_name'):
            from_name = getattr(sage_email.from_address, 'display_name', "") or ""
        
        # Parse date
        date = None
        if sage_email.date:
            try:
                if isinstance(sage_email.date, str):
                    # Handle ISO format with Z
                    date_str = sage_email.date.replace('Z', '+00:00')
                    date = datetime.fromisoformat(date_str)
                else:
                    date = sage_email.date
            except (ValueError, AttributeError) as e:
                logger.warning(f"Failed to parse email date '{sage_email.date}': {e}")
        
        # Convert flags
        flags = sage_email.flags or []
        
        return {
            'mailbox': mailbox,
            'uid': uid,
            'message_id': sage_email.message_id,
            'subject': sage_email.subject or "",
            'from_address': from_address,
            'from_name': from_name,
            'to_addresses': to_addresses,
            'cc_addresses': cc_addresses,
            'bcc_addresses': bcc_addresses,
            'date': date,
            'size': getattr(sage_email, 'size', 0),
            'plain_body': sage_email.plain_body or "",
            'html_body': sage_email.html_body or "",
            'headers': sage_email.headers or {},
            'raw_content': sage_email.raw,
            'is_seen': Flag.SEEN in flags,
            'is_answered': Flag.ANSWERED in flags,
            'is_flagged': Flag.FLAGGED in flags,
            'is_deleted': Flag.DELETED in flags,
            'is_draft': Flag.DRAFT in flags,
            'is_recent': Flag.RECENT in flags,
        }
    
    @staticmethod
    def django_to_sage_email(django_email) -> SageEmailMessage:
        """
        Convert Django Email to sage_imap EmailMessage.
        
        Args:
            django_email: Django Email instance
            
        Returns:
            SageEmailMessage instance
        """
        # Convert addresses
        to_addresses = [EmailAddress(addr) for addr in django_email.to_addresses] if django_email.to_addresses else []
        cc_addresses = [EmailAddress(addr) for addr in django_email.cc_addresses] if django_email.cc_addresses else []
        bcc_addresses = [EmailAddress(addr) for addr in django_email.bcc_addresses] if django_email.bcc_addresses else []
        
        from_address = EmailAddress(django_email.from_address) if django_email.from_address else None
        
        # Convert date
        date = EmailDate(django_email.date.isoformat()) if django_email.date else None
        
        # Convert flags
        flags = []
        if django_email.is_seen:
            flags.append(Flag.SEEN)
        if django_email.is_answered:
            flags.append(Flag.ANSWERED)
        if django_email.is_flagged:
            flags.append(Flag.FLAGGED)
        if django_email.is_deleted:
            flags.append(Flag.DELETED)
        if django_email.is_draft:
            flags.append(Flag.DRAFT)
        if django_email.is_recent:
            flags.append(Flag.RECENT)
        
        # Convert attachments
        attachments = []
        for attachment in django_email.attachments.all():
            sage_attachment = AttachmentConverter.django_to_sage_attachment(attachment)
            attachments.append(sage_attachment)
        
        return SageEmailMessage(
            message_id=django_email.message_id,
            subject=django_email.subject,
            from_address=from_address,
            to_address=to_addresses,
            cc_address=cc_addresses,
            bcc_address=bcc_addresses,
            date=date,
            raw=django_email.raw_content,
            plain_body=django_email.plain_body,
            html_body=django_email.html_body,
            headers=django_email.headers,
            flags=flags,
            attachments=attachments,
            size=django_email.size,
        )
    
    @staticmethod
    def sage_to_django_attachment(sage_attachment: SageAttachment, django_email) -> Dict[str, Any]:
        """
        Convert sage_imap Attachment to Django Attachment field dictionary.
        
        Args:
            sage_attachment: SageAttachment instance
            django_email: Django Email instance
            
        Returns:
            Dictionary with Django Attachment field values
        """
        # Calculate checksum
        checksum = hashlib.sha256(sage_attachment.payload).hexdigest()
        
        return {
            'email': django_email,
            'filename': sage_attachment.filename,
            'content_type': sage_attachment.content_type,
            'size': len(sage_attachment.payload),
            'content_id': sage_attachment.content_id,
            'content_transfer_encoding': sage_attachment.content_transfer_encoding,
            'checksum': checksum,
        }


class AttachmentConverter:
    """Handles attachment conversion and file operations."""
    
    @staticmethod
    def django_to_sage_attachment(django_attachment) -> SageAttachment:
        """
        Convert Django Attachment to sage_imap Attachment.
        
        Args:
            django_attachment: Django Attachment instance
            
        Returns:
            SageAttachment instance
        """
        # Read file content
        payload = b""
        if django_attachment.file_path:
            try:
                if hasattr(django_attachment.file_path, 'read'):
                    payload = django_attachment.file_path.read()
                else:
                    with open(django_attachment.file_path.path, 'rb') as f:
                        payload = f.read()
            except (FileNotFoundError, OSError) as e:
                logger.warning(f"Failed to read attachment file: {e}")
        
        return SageAttachment(
            filename=django_attachment.filename,
            content_type=django_attachment.content_type,
            payload=payload,
            id=str(django_attachment.id),
            content_id=django_attachment.content_id,
            content_transfer_encoding=django_attachment.content_transfer_encoding,
        )
    
    @staticmethod
    def save_attachment_file(attachment, payload: bytes) -> str:
        """
        Save attachment file to storage.
        
        Args:
            attachment: Django Attachment instance
            payload: File content bytes
            
        Returns:
            File path
        """
        # Create safe filename
        safe_filename = FileUtils.sanitize_filename(attachment.filename)
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{safe_filename}"
        
        # Create upload path
        upload_path = f"attachments/{timezone.now().strftime('%Y/%m/%d')}/{filename}"
        
        # Save file
        file_content = ContentFile(payload, name=filename)
        path = default_storage.save(upload_path, file_content)
        
        logger.info(f"Saved attachment file: {path}")
        return path


class FileUtils:
    """Utility functions for file operations."""
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to prevent security issues.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove path components
        filename = os.path.basename(filename)
        
        # Remove dangerous characters
        filename = slugify(filename, allow_unicode=True)
        
        # Ensure extension is preserved
        parts = filename.split('.')
        if len(parts) > 1:
            name = '.'.join(parts[:-1])
            ext = parts[-1]
            filename = f"{name}.{ext}"
        
        # Limit length
        if len(filename) > 255:
            name_part = filename[:200]
            ext_part = filename[-50:]
            filename = f"{name_part}...{ext_part}"
        
        return filename
    
    @staticmethod
    def get_file_type(filename: str) -> str:
        """
        Get file type from filename.
        
        Args:
            filename: Filename
            
        Returns:
            MIME type
        """
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "application/octet-stream"
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """
        Format file size in human readable format.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Formatted size string
        """
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    @staticmethod
    def create_zip_file(files: List[Tuple[str, bytes]], zip_filename: str) -> bytes:
        """
        Create ZIP file from list of files.
        
        Args:
            files: List of (filename, content) tuples
            zip_filename: Name for the ZIP file
            
        Returns:
            ZIP file content as bytes
        """
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filename, content in files:
                zip_file.writestr(filename, content)
        
        zip_buffer.seek(0)
        return zip_buffer.read()
    
    @staticmethod
    def extract_zip_file(zip_content: bytes) -> List[Tuple[str, bytes]]:
        """
        Extract files from ZIP content.
        
        Args:
            zip_content: ZIP file content as bytes
            
        Returns:
            List of (filename, content) tuples
        """
        files = []
        zip_buffer = BytesIO(zip_content)
        
        with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
            for filename in zip_file.namelist():
                if not filename.endswith('/'):  # Skip directories
                    content = zip_file.read(filename)
                    files.append((filename, content))
        
        return files


class SecurityUtils:
    """Security-related utility functions."""
    
    @staticmethod
    def encrypt_password(password: str) -> str:
        """
        Encrypt password for storage.
        
        Args:
            password: Plain text password
            
        Returns:
            Encrypted password
        """
        # Simple encryption - in production, use proper encryption
        from django.contrib.auth.hashers import make_password
        return make_password(password)
    
    @staticmethod
    def decrypt_password(encrypted_password: str) -> str:
        """
        Decrypt password from storage.
        
        Args:
            encrypted_password: Encrypted password
            
        Returns:
            Plain text password
        """
        # This is a placeholder - implement proper decryption
        # For now, return as is (assuming it's not encrypted)
        return encrypted_password
    
    @staticmethod
    def is_safe_filename(filename: str) -> bool:
        """
        Check if filename is safe.
        
        Args:
            filename: Filename to check
            
        Returns:
            True if safe, False otherwise
        """
        # Check for path traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return False
        
        # Check for dangerous extensions
        dangerous_extensions = ['.exe', '.bat', '.cmd', '.com', '.scr', '.vbs', '.js']
        for ext in dangerous_extensions:
            if filename.lower().endswith(ext):
                return False
        
        return True
    
    @staticmethod
    def sanitize_email_content(content: str) -> str:
        """
        Sanitize email content to prevent XSS.
        
        Args:
            content: Email content
            
        Returns:
            Sanitized content
        """
        # Remove dangerous script tags
        import re
        content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove dangerous event handlers
        content = re.sub(r'on\w+="[^"]*"', '', content, flags=re.IGNORECASE)
        content = re.sub(r"on\w+='[^']*'", '', content, flags=re.IGNORECASE)
        
        return content


class EmailUtils:
    """Email-related utility functions."""
    
    @staticmethod
    def extract_email_address(email_string: str) -> str:
        """
        Extract email address from string like "Name <email@example.com>".
        
        Args:
            email_string: Email string
            
        Returns:
            Email address
        """
        import re
        match = re.search(r'<([^>]+)>', email_string)
        if match:
            return match.group(1)
        return email_string.strip()
    
    @staticmethod
    def extract_display_name(email_string: str) -> str:
        """
        Extract display name from string like "Name <email@example.com>".
        
        Args:
            email_string: Email string
            
        Returns:
            Display name
        """
        import re
        match = re.search(r'^([^<]+)<', email_string)
        if match:
            return match.group(1).strip().strip('"')
        return ""
    
    @staticmethod
    def format_email_address(email: str, name: str = "") -> str:
        """
        Format email address with optional display name.
        
        Args:
            email: Email address
            name: Display name
            
        Returns:
            Formatted email string
        """
        if name:
            return f'"{name}" <{email}>'
        return email
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """
        Check if email address is valid.
        
        Args:
            email: Email address to check
            
        Returns:
            True if valid, False otherwise
        """
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def get_email_domain(email: str) -> str:
        """
        Get domain from email address.
        
        Args:
            email: Email address
            
        Returns:
            Domain name
        """
        return email.split('@')[-1] if '@' in email else ""
    
    @staticmethod
    def truncate_subject(subject: str, max_length: int = 100) -> str:
        """
        Truncate email subject to specified length.
        
        Args:
            subject: Email subject
            max_length: Maximum length
            
        Returns:
            Truncated subject
        """
        if len(subject) <= max_length:
            return subject
        return subject[:max_length - 3] + "..."
    
    @staticmethod
    def clean_email_body(body: str) -> str:
        """
        Clean email body by removing excess whitespace.
        
        Args:
            body: Email body
            
        Returns:
            Cleaned body
        """
        # Remove excessive line breaks
        import re
        body = re.sub(r'\n{3,}', '\n\n', body)
        
        # Remove trailing whitespace from lines
        lines = [line.rstrip() for line in body.split('\n')]
        
        return '\n'.join(lines)


class DateUtils:
    """Date-related utility functions."""
    
    @staticmethod
    def parse_email_date(date_string: str) -> Optional[datetime]:
        """
        Parse email date string to datetime.
        
        Args:
            date_string: Date string
            
        Returns:
            Parsed datetime or None
        """
        if not date_string:
            return None
        
        # Try different date formats
        formats = [
            '%a, %d %b %Y %H:%M:%S %z',  # RFC 2822
            '%d %b %Y %H:%M:%S %z',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue
        
        # Try ISO format
        try:
            return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except ValueError:
            pass
        
        logger.warning(f"Failed to parse date: {date_string}")
        return None
    
    @staticmethod
    def format_email_date(date: datetime) -> str:
        """
        Format datetime for email display.
        
        Args:
            date: Datetime object
            
        Returns:
            Formatted date string
        """
        if not date:
            return ""
        
        # Use localized format
        return date.strftime('%Y-%m-%d %H:%M:%S')
    
    @staticmethod
    def get_relative_time(date: datetime) -> str:
        """
        Get relative time string (e.g., "2 hours ago").
        
        Args:
            date: Datetime object
            
        Returns:
            Relative time string
        """
        if not date:
            return ""
        
        now = timezone.now()
        diff = now - date
        
        if diff.days > 365:
            return f"{diff.days // 365} year{'s' if diff.days // 365 != 1 else ''} ago"
        elif diff.days > 30:
            return f"{diff.days // 30} month{'s' if diff.days // 30 != 1 else ''} ago"
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "Just now"


class MailboxUtils:
    """Mailbox-related utility functions."""
    
    @staticmethod
    def get_default_mailbox_names() -> List[str]:
        """
        Get list of default mailbox names.
        
        Returns:
            List of default mailbox names
        """
        return [mb.value for mb in DefaultMailboxes]
    
    @staticmethod
    def is_default_mailbox(name: str) -> bool:
        """
        Check if mailbox name is a default mailbox.
        
        Args:
            name: Mailbox name
            
        Returns:
            True if default, False otherwise
        """
        return name in MailboxUtils.get_default_mailbox_names()
    
    @staticmethod
    def get_mailbox_icon(name: str) -> str:
        """
        Get icon class for mailbox.
        
        Args:
            name: Mailbox name
            
        Returns:
            Icon class name
        """
        icon_map = {
            DefaultMailboxes.INBOX: 'fa-inbox',
            DefaultMailboxes.SENT: 'fa-paper-plane',
            DefaultMailboxes.DRAFTS: 'fa-edit',
            DefaultMailboxes.TRASH: 'fa-trash',
            DefaultMailboxes.SPAM: 'fa-ban',
            DefaultMailboxes.ARCHIVE: 'fa-archive',
        }
        return icon_map.get(name, 'fa-folder')
    
    @staticmethod
    def build_mailbox_hierarchy(mailboxes: List[Dict]) -> List[Dict]:
        """
        Build hierarchical mailbox structure.
        
        Args:
            mailboxes: List of mailbox dictionaries
            
        Returns:
            Hierarchical structure
        """
        hierarchy = []
        mailbox_dict = {mb['name']: mb for mb in mailboxes}
        
        for mailbox in mailboxes:
            if mailbox.get('parent') is None:
                hierarchy.append(mailbox)
            else:
                parent = mailbox_dict.get(mailbox['parent'])
                if parent:
                    if 'children' not in parent:
                        parent['children'] = []
                    parent['children'].append(mailbox)
        
        return hierarchy


# Convenience functions
def convert_sage_to_django_email(sage_email: SageEmailMessage, mailbox, uid: int) -> Dict[str, Any]:
    """Convenience function for email conversion."""
    return EmailConverter.sage_to_django_email(sage_email, mailbox, uid)


def convert_django_to_sage_email(django_email) -> SageEmailMessage:
    """Convenience function for email conversion."""
    return EmailConverter.django_to_sage_email(django_email)


def sanitize_filename(filename: str) -> str:
    """Convenience function for filename sanitization."""
    return FileUtils.sanitize_filename(filename)


def format_file_size(size_bytes: int) -> str:
    """Convenience function for file size formatting."""
    return FileUtils.format_file_size(size_bytes)


def is_safe_filename(filename: str) -> bool:
    """Convenience function for filename safety check."""
    return SecurityUtils.is_safe_filename(filename) 