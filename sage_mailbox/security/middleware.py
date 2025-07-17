"""
Security middleware for sage_mailbox.

This module provides middleware for handling security aspects of email
operations, including authentication, authorization, and audit logging.
"""

import logging
import time
from typing import Optional, Dict, Any
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)
User = get_user_model()


class EmailSecurityMiddleware(MiddlewareMixin):
    """
    Security middleware for email operations.
    
    This middleware handles:
    - Rate limiting for email operations
    - Audit logging of sensitive operations
    - Security headers
    - Request sanitization
    """
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response
        self.rate_limit_window = getattr(settings, 'SAGE_MAILBOX_RATE_LIMIT_WINDOW', 60)  # 1 minute
        self.rate_limit_requests = getattr(settings, 'SAGE_MAILBOX_RATE_LIMIT_REQUESTS', 60)  # 60 requests per minute
        
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Process incoming requests for security checks."""
        # Skip security checks for non-mailbox requests
        if not self._is_mailbox_request(request):
            return None
            
        # Check rate limiting
        if self._is_rate_limited(request):
            logger.warning(f"Rate limit exceeded for {self._get_client_ip(request)}")
            return self._create_rate_limit_response()
            
        # Audit sensitive operations
        if self._is_sensitive_operation(request):
            self._log_sensitive_operation(request)
            
        # Check permissions for mailbox operations
        if not self._check_mailbox_permissions(request):
            logger.warning(f"Unauthorized mailbox access attempt from {self._get_client_ip(request)}")
            return self._create_unauthorized_response()
            
        return None
        
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Process outgoing responses to add security headers."""
        # Add security headers for mailbox responses
        if self._is_mailbox_request(request):
            response = self._add_security_headers(response)
            
        # Log response for audit
        if self._is_sensitive_operation(request):
            self._log_response_audit(request, response)
            
        return response
        
    def _is_mailbox_request(self, request: HttpRequest) -> bool:
        """Check if the request is for mailbox operations."""
        return (
            request.path.startswith('/admin/sage_mailbox/') or
            'sage_mailbox' in request.path or
            request.path.startswith('/api/mailbox/')
        )
        
    def _is_rate_limited(self, request: HttpRequest) -> bool:
        """Check if the request should be rate limited."""
        if not getattr(settings, 'SAGE_MAILBOX_ENABLE_RATE_LIMITING', True):
            return False
            
        client_ip = self._get_client_ip(request)
        cache_key = f"rate_limit:{client_ip}"
        
        # Get current request count
        request_count = cache.get(cache_key, 0)
        
        if request_count >= self.rate_limit_requests:
            return True
            
        # Increment request count
        cache.set(cache_key, request_count + 1, self.rate_limit_window)
        return False
        
    def _is_sensitive_operation(self, request: HttpRequest) -> bool:
        """Check if the request is for a sensitive operation."""
        sensitive_paths = [
            '/admin/sage_mailbox/imapserver/add/',
            '/admin/sage_mailbox/imapserver/change/',
            '/admin/sage_mailbox/email/actions/',
            '/admin/sage_mailbox/attachment/download/',
            '/api/mailbox/sync/',
            '/api/mailbox/export/',
        ]
        
        # Check for sensitive actions
        sensitive_actions = [
            'sync_emails',
            'export_emails',
            'delete_emails',
            'move_to_trash',
            'upload_eml',
            'download_eml',
        ]
        
        return (
            any(path in request.path for path in sensitive_paths) or
            any(action in request.POST.get('action', '') for action in sensitive_actions) or
            request.method in ['DELETE', 'PUT'] and self._is_mailbox_request(request)
        )
        
    def _check_mailbox_permissions(self, request: HttpRequest) -> bool:
        """Check if user has permission for mailbox operations."""
        # Allow if user is authenticated and has proper permissions
        if isinstance(request.user, AnonymousUser):
            return False
            
        # Check if user has mailbox permissions
        if not request.user.has_perm('sage_mailbox.view_email'):
            return False
            
        # Additional checks for sensitive operations
        if self._is_sensitive_operation(request):
            required_perms = {
                'sync_emails': 'sage_mailbox.sync_emails',
                'export_emails': 'sage_mailbox.export_emails',
                'delete_emails': 'sage_mailbox.delete_email',
                'upload_eml': 'sage_mailbox.upload_eml',
            }
            
            action = request.POST.get('action', '')
            if action in required_perms:
                return request.user.has_perm(required_perms[action])
                
        return True
        
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')
        
    def _create_rate_limit_response(self) -> HttpResponse:
        """Create rate limit exceeded response."""
        return HttpResponse(
            'Rate limit exceeded. Please try again later.',
            status=429,
            content_type='text/plain'
        )
        
    def _create_unauthorized_response(self) -> HttpResponse:
        """Create unauthorized access response."""
        return HttpResponse(
            'Unauthorized access to mailbox operations.',
            status=403,
            content_type='text/plain'
        )
        
    def _add_security_headers(self, response: HttpResponse) -> HttpResponse:
        """Add security headers to response."""
        # Content Security Policy
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'"
        )
        
        # X-Frame-Options
        response['X-Frame-Options'] = 'SAMEORIGIN'
        
        # X-Content-Type-Options
        response['X-Content-Type-Options'] = 'nosniff'
        
        # X-XSS-Protection
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer Policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Strict Transport Security (if HTTPS)
        if getattr(settings, 'SECURE_SSL_REDIRECT', False):
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            
        return response
        
    def _log_sensitive_operation(self, request: HttpRequest):
        """Log sensitive operation for audit purposes."""
        audit_data = {
            'user': request.user.username if not isinstance(request.user, AnonymousUser) else 'anonymous',
            'user_id': request.user.id if not isinstance(request.user, AnonymousUser) else None,
            'path': request.path,
            'method': request.method,
            'ip_address': self._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'timestamp': timezone.now().isoformat(),
            'action': request.POST.get('action', ''),
            'referer': request.META.get('HTTP_REFERER', ''),
        }
        
        logger.info(f"Sensitive operation audit: {audit_data}")
        
        # Store in audit log (example)
        # AuditLog.objects.create(
        #     user=request.user if not isinstance(request.user, AnonymousUser) else None,
        #     action='sensitive_operation',
        #     object_type='mailbox',
        #     data=audit_data,
        #     ip_address=self._get_client_ip(request),
        # )
        
    def _log_response_audit(self, request: HttpRequest, response: HttpResponse):
        """Log response audit information."""
        audit_data = {
            'user': request.user.username if not isinstance(request.user, AnonymousUser) else 'anonymous',
            'path': request.path,
            'method': request.method,
            'status_code': response.status_code,
            'ip_address': self._get_client_ip(request),
            'timestamp': timezone.now().isoformat(),
            'response_size': len(response.content) if hasattr(response, 'content') else 0,
        }
        
        logger.info(f"Response audit: {audit_data}")


class AttachmentSecurityMiddleware(MiddlewareMixin):
    """
    Security middleware for attachment operations.
    
    This middleware handles security for file uploads and downloads.
    """
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response
        self.max_file_size = getattr(settings, 'SAGE_MAILBOX_MAX_FILE_SIZE', 50 * 1024 * 1024)  # 50MB
        self.allowed_extensions = getattr(settings, 'SAGE_MAILBOX_ALLOWED_EXTENSIONS', [
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.txt', '.csv', '.zip', '.rar', '.7z',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg',
            '.mp3', '.mp4', '.avi', '.mov', '.wmv',
            '.eml', '.msg'
        ])
        
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Process attachment requests for security checks."""
        if not self._is_attachment_request(request):
            return None
            
        # Check file upload security
        if request.method == 'POST' and request.FILES:
            validation_result = self._validate_file_upload(request)
            if validation_result:
                return validation_result
                
        return None
        
    def _is_attachment_request(self, request: HttpRequest) -> bool:
        """Check if request is for attachment operations."""
        return (
            'attachment' in request.path or
            'upload_eml' in request.path or
            'download' in request.path
        )
        
    def _validate_file_upload(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Validate file upload security."""
        for field_name, uploaded_file in request.FILES.items():
            # Check file size
            if uploaded_file.size > self.max_file_size:
                logger.warning(f"File too large: {uploaded_file.name} ({uploaded_file.size} bytes)")
                return HttpResponse(
                    f'File too large. Maximum size is {self.max_file_size} bytes.',
                    status=413,
                    content_type='text/plain'
                )
                
            # Check file extension
            if not self._is_allowed_extension(uploaded_file.name):
                logger.warning(f"Disallowed file extension: {uploaded_file.name}")
                return HttpResponse(
                    f'File type not allowed. Allowed extensions: {", ".join(self.allowed_extensions)}',
                    status=400,
                    content_type='text/plain'
                )
                
            # Check file content (basic magic number check)
            if not self._validate_file_content(uploaded_file):
                logger.warning(f"Suspicious file content: {uploaded_file.name}")
                return HttpResponse(
                    'File content validation failed.',
                    status=400,
                    content_type='text/plain'
                )
                
        return None
        
    def _is_allowed_extension(self, filename: str) -> bool:
        """Check if file extension is allowed."""
        import os
        ext = os.path.splitext(filename)[1].lower()
        return ext in self.allowed_extensions
        
    def _validate_file_content(self, uploaded_file) -> bool:
        """Validate file content using magic numbers."""
        try:
            # Read first few bytes to check magic numbers
            uploaded_file.seek(0)
            header = uploaded_file.read(1024)
            uploaded_file.seek(0)
            
            # Basic magic number checks
            magic_numbers = {
                b'\x25\x50\x44\x46': '.pdf',
                b'\x50\x4B\x03\x04': '.zip',
                b'\x50\x4B\x05\x06': '.zip',
                b'\x50\x4B\x07\x08': '.zip',
                b'\xFF\xD8\xFF': '.jpg',
                b'\x89\x50\x4E\x47': '.png',
                b'\x47\x49\x46\x38': '.gif',
                b'\xD0\xCF\x11\xE0': '.doc',  # MS Office
            }
            
            # Check if file starts with known magic numbers
            filename_ext = os.path.splitext(uploaded_file.name)[1].lower()
            
            for magic, ext in magic_numbers.items():
                if header.startswith(magic):
                    # If magic number matches expected extension, it's valid
                    if filename_ext == ext or filename_ext == '.docx' and ext == '.doc':
                        return True
                    # If magic number doesn't match extension, it's suspicious
                    return False
                    
            # For text files and other formats, allow if extension is in allowed list
            if filename_ext in ['.txt', '.csv', '.eml', '.msg']:
                return True
                
            return True  # Default to allow if no magic number match
            
        except Exception as e:
            logger.error(f"Error validating file content: {e}")
            return False


class EmailContentSecurityMiddleware(MiddlewareMixin):
    """
    Security middleware for email content handling.
    
    This middleware handles security for email content display and processing.
    """
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response
        
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Process email content responses for security."""
        if not self._is_email_content_response(request, response):
            return response
            
        # Sanitize email content in response
        if hasattr(response, 'content'):
            response.content = self._sanitize_email_content(response.content)
            
        return response
        
    def _is_email_content_response(self, request: HttpRequest, response: HttpResponse) -> bool:
        """Check if response contains email content."""
        return (
            'email' in request.path and
            response.get('Content-Type', '').startswith('text/html')
        )
        
    def _sanitize_email_content(self, content: bytes) -> bytes:
        """Sanitize email content for safe display."""
        try:
            # This is a basic example - in production you'd use a proper HTML sanitizer
            # like bleach or similar
            
            content_str = content.decode('utf-8', errors='ignore')
            
            # Remove dangerous HTML elements
            dangerous_tags = [
                '<script', '</script>',
                '<object', '</object>',
                '<embed', '</embed>',
                '<applet', '</applet>',
                '<iframe', '</iframe>',
                '<form', '</form>',
            ]
            
            for tag in dangerous_tags:
                content_str = content_str.replace(tag, f'&lt;{tag[1:]}')
                
            # Remove javascript: URLs
            content_str = content_str.replace('javascript:', 'blocked:')
            
            # Remove data: URLs for images (optional, depending on security requirements)
            # content_str = content_str.replace('data:', 'blocked:')
            
            return content_str.encode('utf-8')
            
        except Exception as e:
            logger.error(f"Error sanitizing email content: {e}")
            return content


def get_security_context(request: HttpRequest) -> Dict[str, Any]:
    """Get security context for the current request."""
    return {
        'user_authenticated': not isinstance(request.user, AnonymousUser),
        'user_id': request.user.id if not isinstance(request.user, AnonymousUser) else None,
        'user_permissions': list(request.user.get_all_permissions()) if not isinstance(request.user, AnonymousUser) else [],
        'client_ip': request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')),
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'is_secure': request.is_secure(),
        'timestamp': timezone.now().isoformat(),
    }


def log_security_event(event_type: str, message: str, user=None, additional_data: Dict[str, Any] = None):
    """Log security-related events."""
    log_data = {
        'event_type': event_type,
        'message': message,
        'user': user.username if user and not isinstance(user, AnonymousUser) else 'anonymous',
        'timestamp': timezone.now().isoformat(),
    }
    
    if additional_data:
        log_data.update(additional_data)
        
    logger.warning(f"Security event: {log_data}")
    
    # Store in security audit log
    # SecurityAuditLog.objects.create(
    #     event_type=event_type,
    #     message=message,
    #     user=user if user and not isinstance(user, AnonymousUser) else None,
    #     data=log_data,
    # ) 