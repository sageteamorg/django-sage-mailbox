"""
Permission classes for sage_mailbox.

This module provides permission checking and access control
for email operations and mailbox access.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from ..models import IMAPServer, Mailbox, Email, Attachment

logger = logging.getLogger(__name__)


class EmailPermissions:
    """
    Permission checking utilities for email operations.
    
    This class provides methods to check user permissions
    for various email-related operations.
    """
    
    @staticmethod
    def can_view_email(user: User, email: Email) -> bool:
        """
        Check if user can view a specific email.
        
        Args:
            user: User to check permissions for
            email: Email to check access to
            
        Returns:
            True if user can view email, False otherwise
        """
        if not user.is_authenticated:
            return False
            
        # Superuser can view all emails
        if user.is_superuser:
            return True
            
        # Check basic permission
        if not user.has_perm('sage_mailbox.view_email'):
            return False
            
        # Check if user owns the mailbox server
        if email.mailbox.server.owner == user:
            return True
            
        # Check if user is in allowed groups for this server
        if EmailPermissions._check_server_group_access(user, email.mailbox.server):
            return True
            
        return False
        
    @staticmethod
    def can_edit_email(user: User, email: Email) -> bool:
        """
        Check if user can edit a specific email.
        
        Args:
            user: User to check permissions for
            email: Email to check access to
            
        Returns:
            True if user can edit email, False otherwise
        """
        if not user.is_authenticated:
            return False
            
        # Superuser can edit all emails
        if user.is_superuser:
            return True
            
        # Check basic permission
        if not user.has_perm('sage_mailbox.change_email'):
            return False
            
        # Check if user owns the mailbox server
        if email.mailbox.server.owner == user:
            return True
            
        # Check if user is in allowed groups for this server
        if EmailPermissions._check_server_group_access(user, email.mailbox.server):
            return True
            
        return False
        
    @staticmethod
    def can_delete_email(user: User, email: Email) -> bool:
        """
        Check if user can delete a specific email.
        
        Args:
            user: User to check permissions for
            email: Email to check access to
            
        Returns:
            True if user can delete email, False otherwise
        """
        if not user.is_authenticated:
            return False
            
        # Superuser can delete all emails
        if user.is_superuser:
            return True
            
        # Check basic permission
        if not user.has_perm('sage_mailbox.delete_email'):
            return False
            
        # Check if user owns the mailbox server
        if email.mailbox.server.owner == user:
            return True
            
        # Check if user is in allowed groups for this server
        if EmailPermissions._check_server_group_access(user, email.mailbox.server):
            return True
            
        return False
        
    @staticmethod
    def can_sync_mailbox(user: User, mailbox: Mailbox) -> bool:
        """
        Check if user can sync a specific mailbox.
        
        Args:
            user: User to check permissions for
            mailbox: Mailbox to check access to
            
        Returns:
            True if user can sync mailbox, False otherwise
        """
        if not user.is_authenticated:
            return False
            
        # Superuser can sync all mailboxes
        if user.is_superuser:
            return True
            
        # Check custom permission
        if not user.has_perm('sage_mailbox.sync_emails'):
            return False
            
        # Check if user owns the mailbox server
        if mailbox.server.owner == user:
            return True
            
        # Check if user is in allowed groups for this server
        if EmailPermissions._check_server_group_access(user, mailbox.server):
            return True
            
        return False
        
    @staticmethod
    def can_view_attachment(user: User, attachment: Attachment) -> bool:
        """
        Check if user can view a specific attachment.
        
        Args:
            user: User to check permissions for
            attachment: Attachment to check access to
            
        Returns:
            True if user can view attachment, False otherwise
        """
        if not user.is_authenticated:
            return False
            
        # Check if user can view the associated email
        return EmailPermissions.can_view_email(user, attachment.email)
        
    @staticmethod
    def can_download_attachment(user: User, attachment: Attachment) -> bool:
        """
        Check if user can download a specific attachment.
        
        Args:
            user: User to check permissions for
            attachment: Attachment to check access to
            
        Returns:
            True if user can download attachment, False otherwise
        """
        if not user.is_authenticated:
            return False
            
        # Check basic permission
        if not user.has_perm('sage_mailbox.download_attachment'):
            return False
            
        # Check if user can view the associated email
        return EmailPermissions.can_view_email(user, attachment.email)
        
    @staticmethod
    def can_upload_eml(user: User, server: IMAPServer) -> bool:
        """
        Check if user can upload EML files to a server.
        
        Args:
            user: User to check permissions for
            server: IMAP server to check access to
            
        Returns:
            True if user can upload EML files, False otherwise
        """
        if not user.is_authenticated:
            return False
            
        # Superuser can upload to all servers
        if user.is_superuser:
            return True
            
        # Check custom permission
        if not user.has_perm('sage_mailbox.upload_eml'):
            return False
            
        # Check if user owns the server
        if server.owner == user:
            return True
            
        # Check if user is in allowed groups for this server
        if EmailPermissions._check_server_group_access(user, server):
            return True
            
        return False
        
    @staticmethod
    def can_export_emails(user: User, server: IMAPServer) -> bool:
        """
        Check if user can export emails from a server.
        
        Args:
            user: User to check permissions for
            server: IMAP server to check access to
            
        Returns:
            True if user can export emails, False otherwise
        """
        if not user.is_authenticated:
            return False
            
        # Superuser can export from all servers
        if user.is_superuser:
            return True
            
        # Check custom permission
        if not user.has_perm('sage_mailbox.export_emails'):
            return False
            
        # Check if user owns the server
        if server.owner == user:
            return True
            
        # Check if user is in allowed groups for this server
        if EmailPermissions._check_server_group_access(user, server):
            return True
            
        return False
        
    @staticmethod
    def can_manage_server(user: User, server: IMAPServer) -> bool:
        """
        Check if user can manage a specific IMAP server.
        
        Args:
            user: User to check permissions for
            server: IMAP server to check access to
            
        Returns:
            True if user can manage server, False otherwise
        """
        if not user.is_authenticated:
            return False
            
        # Superuser can manage all servers
        if user.is_superuser:
            return True
            
        # Check basic permission
        if not user.has_perm('sage_mailbox.change_imapserver'):
            return False
            
        # Check if user owns the server
        if server.owner == user:
            return True
            
        return False
        
    @staticmethod
    def get_accessible_servers(user: User) -> List[IMAPServer]:
        """
        Get list of IMAP servers accessible to a user.
        
        Args:
            user: User to check permissions for
            
        Returns:
            List of accessible IMAP servers
        """
        if not user.is_authenticated:
            return []
            
        # Superuser can access all servers
        if user.is_superuser:
            return list(IMAPServer.objects.all())
            
        # Get servers owned by user
        owned_servers = IMAPServer.objects.filter(owner=user)
        
        # Get servers accessible through groups
        group_servers = IMAPServer.objects.filter(
            id__in=EmailPermissions._get_group_accessible_server_ids(user)
        )
        
        # Combine and deduplicate
        accessible_servers = list(owned_servers.union(group_servers))
        
        return accessible_servers
        
    @staticmethod
    def get_accessible_mailboxes(user: User) -> List[Mailbox]:
        """
        Get list of mailboxes accessible to a user.
        
        Args:
            user: User to check permissions for
            
        Returns:
            List of accessible mailboxes
        """
        accessible_servers = EmailPermissions.get_accessible_servers(user)
        server_ids = [server.id for server in accessible_servers]
        
        return list(Mailbox.objects.filter(server_id__in=server_ids))
        
    @staticmethod
    def get_accessible_emails(user: User) -> List[Email]:
        """
        Get list of emails accessible to a user.
        
        Args:
            user: User to check permissions for
            
        Returns:
            List of accessible emails
        """
        accessible_mailboxes = EmailPermissions.get_accessible_mailboxes(user)
        mailbox_ids = [mailbox.id for mailbox in accessible_mailboxes]
        
        return list(Email.objects.filter(mailbox_id__in=mailbox_ids))
        
    @staticmethod
    def _check_server_group_access(user: User, server: IMAPServer) -> bool:
        """
        Check if user has access to server through group membership.
        
        Args:
            user: User to check
            server: Server to check access to
            
        Returns:
            True if user has group access, False otherwise
        """
        # This is a placeholder for group-based access control
        # You could implement this based on your specific requirements
        
        # Example implementation:
        # 1. Check if server has associated groups
        # 2. Check if user is member of any of those groups
        
        # For now, return False as group access is not implemented
        return False
        
    @staticmethod
    def _get_group_accessible_server_ids(user: User) -> List[int]:
        """
        Get list of server IDs accessible through group membership.
        
        Args:
            user: User to check
            
        Returns:
            List of server IDs
        """
        # This is a placeholder for group-based access control
        # You could implement this based on your specific requirements
        
        return []
        
    @staticmethod
    def filter_emails_by_permission(user: User, emails: List[Email]) -> List[Email]:
        """
        Filter emails based on user permissions.
        
        Args:
            user: User to check permissions for
            emails: List of emails to filter
            
        Returns:
            List of emails user can access
        """
        if not user.is_authenticated:
            return []
            
        # Superuser can access all emails
        if user.is_superuser:
            return emails
            
        accessible_emails = []
        for email in emails:
            if EmailPermissions.can_view_email(user, email):
                accessible_emails.append(email)
                
        return accessible_emails
        
    @staticmethod
    def require_permission(permission: str, obj: Any = None):
        """
        Decorator to require specific permission for a view or function.
        
        Args:
            permission: Permission string (e.g., 'sage_mailbox.view_email')
            obj: Object to check permission against (optional)
            
        Returns:
            Decorator function
        """
        def decorator(func):
            def wrapper(request, *args, **kwargs):
                if not request.user.is_authenticated:
                    raise PermissionDenied(_('Authentication required'))
                    
                if not request.user.has_perm(permission, obj):
                    raise PermissionDenied(_('Permission denied'))
                    
                return func(request, *args, **kwargs)
            return wrapper
        return decorator


class PermissionManager:
    """
    Manager for creating and managing custom permissions.
    
    This class provides utilities for creating and managing
    custom permissions for sage_mailbox.
    """
    
    @staticmethod
    def create_custom_permissions():
        """
        Create custom permissions for sage_mailbox.
        
        This method creates additional permissions beyond the default
        Django model permissions.
        """
        # Get content types
        email_ct = ContentType.objects.get_for_model(Email)
        mailbox_ct = ContentType.objects.get_for_model(Mailbox)
        server_ct = ContentType.objects.get_for_model(IMAPServer)
        attachment_ct = ContentType.objects.get_for_model(Attachment)
        
        # Custom permissions to create
        custom_permissions = [
            # Email permissions
            ('sync_emails', 'Can sync emails', email_ct),
            ('export_emails', 'Can export emails', email_ct),
            ('upload_eml', 'Can upload EML files', email_ct),
            ('download_eml', 'Can download EML files', email_ct),
            ('bulk_delete_emails', 'Can bulk delete emails', email_ct),
            ('restore_emails', 'Can restore deleted emails', email_ct),
            
            # Mailbox permissions
            ('sync_mailbox', 'Can sync mailbox', mailbox_ct),
            ('create_mailbox', 'Can create mailbox', mailbox_ct),
            ('delete_mailbox', 'Can delete mailbox', mailbox_ct),
            
            # Server permissions
            ('test_server_connection', 'Can test server connection', server_ct),
            ('manage_server_settings', 'Can manage server settings', server_ct),
            ('view_server_stats', 'Can view server statistics', server_ct),
            
            # Attachment permissions
            ('download_attachment', 'Can download attachments', attachment_ct),
            ('bulk_download_attachments', 'Can bulk download attachments', attachment_ct),
            ('delete_attachment', 'Can delete attachments', attachment_ct),
        ]
        
        # Create permissions
        for codename, name, content_type in custom_permissions:
            permission, created = Permission.objects.get_or_create(
                codename=codename,
                name=name,
                content_type=content_type,
            )
            
            if created:
                logger.info(f"Created custom permission: {codename}")
            else:
                logger.debug(f"Custom permission already exists: {codename}")
                
    @staticmethod
    def create_default_groups():
        """
        Create default groups with appropriate permissions.
        
        This method creates default groups for different user roles.
        """
        # Email Admin group
        email_admin_group, created = Group.objects.get_or_create(
            name='Email Administrators'
        )
        
        if created:
            # Add permissions to Email Admin group
            admin_permissions = [
                'view_email', 'add_email', 'change_email', 'delete_email',
                'view_mailbox', 'add_mailbox', 'change_mailbox', 'delete_mailbox',
                'view_imapserver', 'add_imapserver', 'change_imapserver', 'delete_imapserver',
                'view_attachment', 'add_attachment', 'change_attachment', 'delete_attachment',
                'sync_emails', 'export_emails', 'upload_eml', 'download_eml',
                'bulk_delete_emails', 'restore_emails', 'sync_mailbox',
                'test_server_connection', 'manage_server_settings', 'view_server_stats',
                'download_attachment', 'bulk_download_attachments', 'delete_attachment',
            ]
            
            for perm_codename in admin_permissions:
                try:
                    permission = Permission.objects.get(codename=perm_codename)
                    email_admin_group.permissions.add(permission)
                except Permission.DoesNotExist:
                    logger.warning(f"Permission {perm_codename} not found")
                    
            logger.info("Created Email Administrators group")
            
        # Email User group
        email_user_group, created = Group.objects.get_or_create(
            name='Email Users'
        )
        
        if created:
            # Add permissions to Email User group
            user_permissions = [
                'view_email', 'view_mailbox', 'view_attachment',
                'download_attachment', 'export_emails', 'download_eml',
            ]
            
            for perm_codename in user_permissions:
                try:
                    permission = Permission.objects.get(codename=perm_codename)
                    email_user_group.permissions.add(permission)
                except Permission.DoesNotExist:
                    logger.warning(f"Permission {perm_codename} not found")
                    
            logger.info("Created Email Users group")
            
        # Email Viewer group (read-only)
        email_viewer_group, created = Group.objects.get_or_create(
            name='Email Viewers'
        )
        
        if created:
            # Add permissions to Email Viewer group
            viewer_permissions = [
                'view_email', 'view_mailbox', 'view_attachment',
            ]
            
            for perm_codename in viewer_permissions:
                try:
                    permission = Permission.objects.get(codename=perm_codename)
                    email_viewer_group.permissions.add(permission)
                except Permission.DoesNotExist:
                    logger.warning(f"Permission {perm_codename} not found")
                    
            logger.info("Created Email Viewers group")
            
    @staticmethod
    def assign_user_to_group(user: User, group_name: str):
        """
        Assign user to a specific group.
        
        Args:
            user: User to assign
            group_name: Name of the group
        """
        try:
            group = Group.objects.get(name=group_name)
            user.groups.add(group)
            logger.info(f"Added user {user.username} to group {group_name}")
        except Group.DoesNotExist:
            logger.error(f"Group {group_name} does not exist")
            
    @staticmethod
    def remove_user_from_group(user: User, group_name: str):
        """
        Remove user from a specific group.
        
        Args:
            user: User to remove
            group_name: Name of the group
        """
        try:
            group = Group.objects.get(name=group_name)
            user.groups.remove(group)
            logger.info(f"Removed user {user.username} from group {group_name}")
        except Group.DoesNotExist:
            logger.error(f"Group {group_name} does not exist")
            
    @staticmethod
    def get_user_permissions(user: User) -> List[str]:
        """
        Get list of all permissions for a user.
        
        Args:
            user: User to check permissions for
            
        Returns:
            List of permission codenames
        """
        if not user.is_authenticated:
            return []
            
        # Get all permissions (direct and through groups)
        permissions = user.get_all_permissions()
        
        # Filter for sage_mailbox permissions
        mailbox_permissions = [
            perm for perm in permissions 
            if perm.startswith('sage_mailbox.')
        ]
        
        return mailbox_permissions


# Initialize permission manager
permission_manager = PermissionManager() 