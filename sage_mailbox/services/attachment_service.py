"""
Attachment service for sage_mailbox.

This module provides comprehensive attachment handling including
file storage, security checks, and conversion utilities.
"""

import hashlib
import logging
import mimetypes
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

from sage_imap.models.email import Attachment as SageAttachment

from ..models import Email, Attachment
from ..utils import FileUtils, SecurityUtils, format_file_size
from ..validators import validate_filename, validate_file_size, validate_content_type

logger = logging.getLogger(__name__)


class AttachmentService:
    """Service for handling email attachments."""
    
    def __init__(self):
        self.storage = default_storage
        self.max_size = getattr(settings, 'SAGE_MAILBOX_MAX_ATTACHMENT_SIZE', 25 * 1024 * 1024)
        self.upload_path = getattr(settings, 'SAGE_MAILBOX_ATTACHMENT_PATH', 'attachments')
        self.allowed_extensions = getattr(settings, 'SAGE_MAILBOX_ALLOWED_EXTENSIONS', [])
        self.blocked_extensions = getattr(settings, 'SAGE_MAILBOX_BLOCKED_EXTENSIONS', [
            '.exe', '.bat', '.cmd', '.com', '.scr', '.vbs', '.js', '.jar'
        ])
    
    def create_from_sage_attachment(self, email: Email, sage_attachment: SageAttachment) -> Attachment:
        """
        Create Django Attachment from sage_imap Attachment.
        
        Args:
            email: Email instance to attach to
            sage_attachment: SageAttachment instance
            
        Returns:
            Created Attachment instance
        """
        # Validate attachment
        self._validate_attachment(sage_attachment)
        
        # Create attachment record
        attachment = Attachment(
            email=email,
            filename=sage_attachment.filename,
            content_type=sage_attachment.content_type,
            size=len(sage_attachment.payload),
            content_id=sage_attachment.content_id,
            content_transfer_encoding=sage_attachment.content_transfer_encoding,
            checksum=hashlib.sha256(sage_attachment.payload).hexdigest(),
        )
        
        # Save file
        file_path = self._save_attachment_file(attachment, sage_attachment.payload)
        attachment.file_path = file_path
        
        # Save to database
        attachment.save()
        
        logger.info(f"Created attachment: {attachment.filename} ({format_file_size(attachment.size)})")
        return attachment
    
    def save_attachment_file(self, attachment: Attachment, content: bytes) -> str:
        """
        Save attachment file to storage.
        
        Args:
            attachment: Attachment instance
            content: File content bytes
            
        Returns:
            Saved file path
        """
        return self._save_attachment_file(attachment, content)
    
    def _save_attachment_file(self, attachment: Attachment, content: bytes) -> str:
        """Save attachment file to storage."""
        # Create safe filename
        safe_filename = self._generate_safe_filename(attachment.filename)
        
        # Create upload path with date structure
        date_path = timezone.now().strftime('%Y/%m/%d')
        upload_path = f"{self.upload_path}/{date_path}/{safe_filename}"
        
        # Save file
        file_content = ContentFile(content, name=safe_filename)
        path = self.storage.save(upload_path, file_content)
        
        logger.debug(f"Saved attachment file: {path}")
        return path
    
    def _generate_safe_filename(self, filename: str) -> str:
        """Generate a safe filename with timestamp."""
        # Sanitize filename
        safe_name = FileUtils.sanitize_filename(filename)
        
        # Add timestamp to prevent collisions
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S_%f')
        name, ext = os.path.splitext(safe_name)
        
        return f"{timestamp}_{name}{ext}"
    
    def _validate_attachment(self, sage_attachment: SageAttachment):
        """Validate attachment before saving."""
        # Check filename
        validate_filename(sage_attachment.filename)
        
        # Check if filename is safe
        if not SecurityUtils.is_safe_filename(sage_attachment.filename):
            raise ValueError(f"Unsafe filename: {sage_attachment.filename}")
        
        # Check file size
        validate_file_size(len(sage_attachment.payload), self.max_size)
        
        # Check content type
        validate_content_type(sage_attachment.content_type)
        
        # Check extension
        self._validate_extension(sage_attachment.filename)
    
    def _validate_extension(self, filename: str):
        """Validate file extension."""
        _, ext = os.path.splitext(filename.lower())
        
        # Check blocked extensions
        if ext in self.blocked_extensions:
            raise ValueError(f"Blocked file extension: {ext}")
        
        # Check allowed extensions (if specified)
        if self.allowed_extensions and ext not in self.allowed_extensions:
            raise ValueError(f"File extension not allowed: {ext}")
    
    def get_attachment_url(self, attachment: Attachment) -> Optional[str]:
        """Get URL for attachment file."""
        if attachment.file_path:
            try:
                return self.storage.url(attachment.file_path.name)
            except Exception as e:
                logger.error(f"Failed to get URL for attachment {attachment.filename}: {e}")
        return None
    
    def download_attachment(self, attachment: Attachment) -> Optional[bytes]:
        """Download attachment content."""
        if not attachment.file_path:
            return None
        
        try:
            with attachment.file_path.open('rb') as f:
                content = f.read()
            
            # Verify integrity if checksum is available
            if attachment.checksum:
                calculated_checksum = hashlib.sha256(content).hexdigest()
                if calculated_checksum != attachment.checksum:
                    logger.error(f"Checksum mismatch for attachment {attachment.filename}")
                    return None
            
            return content
            
        except Exception as e:
            logger.error(f"Failed to download attachment {attachment.filename}: {e}")
            return None
    
    def delete_attachment_file(self, attachment: Attachment) -> bool:
        """Delete attachment file from storage."""
        if not attachment.file_path:
            return True
        
        try:
            self.storage.delete(attachment.file_path.name)
            logger.info(f"Deleted attachment file: {attachment.file_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete attachment file {attachment.file_path.name}: {e}")
            return False
    
    def verify_attachment_integrity(self, attachment: Attachment) -> bool:
        """Verify attachment file integrity."""
        if not attachment.file_path or not attachment.checksum:
            return True  # Can't verify without file or checksum
        
        try:
            content = self.download_attachment(attachment)
            if content is None:
                return False
            
            calculated_checksum = hashlib.sha256(content).hexdigest()
            return calculated_checksum == attachment.checksum
            
        except Exception as e:
            logger.error(f"Failed to verify attachment integrity {attachment.filename}: {e}")
            return False
    
    def get_attachment_info(self, attachment: Attachment) -> Dict:
        """Get comprehensive attachment information."""
        info = {
            'filename': attachment.filename,
            'size': attachment.size,
            'size_formatted': format_file_size(attachment.size),
            'content_type': attachment.content_type,
            'is_image': attachment.is_image,
            'is_text': attachment.is_text,
            'created_at': attachment.created_at,
            'checksum': attachment.checksum,
            'file_exists': False,
            'url': None,
        }
        
        # Check if file exists
        if attachment.file_path:
            try:
                info['file_exists'] = self.storage.exists(attachment.file_path.name)
                info['url'] = self.get_attachment_url(attachment)
            except Exception as e:
                logger.error(f"Failed to check attachment existence {attachment.filename}: {e}")
        
        return info
    
    def cleanup_orphaned_attachments(self, dry_run: bool = False) -> Dict:
        """
        Clean up orphaned attachment files.
        
        Args:
            dry_run: If True, only report what would be deleted
            
        Returns:
            Dictionary with cleanup statistics
        """
        stats = {
            'files_checked': 0,
            'orphaned_files': 0,
            'deleted_files': 0,
            'errors': 0,
        }
        
        try:
            # Get all attachment file paths from database
            db_paths = set(
                Attachment.objects.exclude(file_path='').values_list('file_path', flat=True)
            )
            
            # Get all files in attachment storage
            attachment_root = Path(self.upload_path)
            if self.storage.exists(str(attachment_root)):
                # Walk through all files in storage
                for root, dirs, files in os.walk(self.storage.path(str(attachment_root))):
                    for file in files:
                        file_path = os.path.join(root, file)
                        relative_path = os.path.relpath(file_path, self.storage.location)
                        
                        stats['files_checked'] += 1
                        
                        if relative_path not in db_paths:
                            stats['orphaned_files'] += 1
                            
                            if not dry_run:
                                try:
                                    os.remove(file_path)
                                    stats['deleted_files'] += 1
                                    logger.info(f"Deleted orphaned file: {relative_path}")
                                except Exception as e:
                                    logger.error(f"Failed to delete orphaned file {relative_path}: {e}")
                                    stats['errors'] += 1
                            else:
                                logger.info(f"Would delete orphaned file: {relative_path}")
        
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned attachments: {e}")
            stats['errors'] += 1
        
        return stats
    
    def get_storage_statistics(self) -> Dict:
        """Get attachment storage statistics."""
        stats = {
            'total_attachments': 0,
            'total_size': 0,
            'total_files': 0,
            'missing_files': 0,
            'corrupted_files': 0,
            'by_content_type': {},
            'by_extension': {},
            'largest_files': [],
        }
        
        try:
            attachments = Attachment.objects.all()
            
            for attachment in attachments:
                stats['total_attachments'] += 1
                stats['total_size'] += attachment.size
                
                # Count by content type
                content_type = attachment.content_type
                if content_type not in stats['by_content_type']:
                    stats['by_content_type'][content_type] = {'count': 0, 'size': 0}
                stats['by_content_type'][content_type]['count'] += 1
                stats['by_content_type'][content_type]['size'] += attachment.size
                
                # Count by extension
                _, ext = os.path.splitext(attachment.filename.lower())
                if ext not in stats['by_extension']:
                    stats['by_extension'][ext] = {'count': 0, 'size': 0}
                stats['by_extension'][ext]['count'] += 1
                stats['by_extension'][ext]['size'] += attachment.size
                
                # Check file existence
                if attachment.file_path:
                    try:
                        if self.storage.exists(attachment.file_path.name):
                            stats['total_files'] += 1
                            
                            # Check integrity
                            if not self.verify_attachment_integrity(attachment):
                                stats['corrupted_files'] += 1
                        else:
                            stats['missing_files'] += 1
                    except Exception as e:
                        logger.error(f"Error checking attachment {attachment.filename}: {e}")
                        stats['missing_files'] += 1
            
            # Get largest files
            stats['largest_files'] = list(
                attachments.order_by('-size')[:10].values('filename', 'size', 'content_type')
            )
            
        except Exception as e:
            logger.error(f"Failed to get storage statistics: {e}")
        
        return stats
    
    def migrate_attachments(self, new_storage_path: str) -> Dict:
        """
        Migrate attachments to new storage path.
        
        Args:
            new_storage_path: New storage path
            
        Returns:
            Migration statistics
        """
        stats = {
            'total_attachments': 0,
            'migrated_attachments': 0,
            'failed_attachments': 0,
            'errors': [],
        }
        
        try:
            attachments = Attachment.objects.exclude(file_path='')
            
            for attachment in attachments:
                stats['total_attachments'] += 1
                
                try:
                    # Read current file
                    content = self.download_attachment(attachment)
                    if content is None:
                        stats['failed_attachments'] += 1
                        stats['errors'].append(f"Failed to read {attachment.filename}")
                        continue
                    
                    # Save to new location
                    old_path = attachment.file_path.name
                    new_path = os.path.join(new_storage_path, os.path.basename(old_path))
                    
                    file_content = ContentFile(content, name=os.path.basename(old_path))
                    saved_path = self.storage.save(new_path, file_content)
                    
                    # Update attachment record
                    attachment.file_path = saved_path
                    attachment.save()
                    
                    # Delete old file
                    try:
                        self.storage.delete(old_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete old file {old_path}: {e}")
                    
                    stats['migrated_attachments'] += 1
                    logger.info(f"Migrated attachment: {attachment.filename}")
                    
                except Exception as e:
                    stats['failed_attachments'] += 1
                    error_msg = f"Failed to migrate {attachment.filename}: {e}"
                    stats['errors'].append(error_msg)
                    logger.error(error_msg)
        
        except Exception as e:
            error_msg = f"Migration failed: {e}"
            stats['errors'].append(error_msg)
            logger.error(error_msg)
        
        return stats
    
    def bulk_download_attachments(self, attachments: List[Attachment]) -> Optional[bytes]:
        """
        Download multiple attachments as a ZIP file.
        
        Args:
            attachments: List of attachment instances
            
        Returns:
            ZIP file content as bytes
        """
        if not attachments:
            return None
        
        try:
            files = []
            
            for attachment in attachments:
                content = self.download_attachment(attachment)
                if content:
                    files.append((attachment.filename, content))
                else:
                    logger.warning(f"Failed to download attachment: {attachment.filename}")
            
            if files:
                zip_filename = f"attachments_{len(files)}_files.zip"
                return FileUtils.create_zip_file(files, zip_filename)
            
        except Exception as e:
            logger.error(f"Failed to create ZIP file: {e}")
        
        return None 