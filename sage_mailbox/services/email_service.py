"""
Email sending service for sage_mailbox.

This module provides professional email sending capabilities with proper
Message-ID generation, Outlook-compatible headers, and best practices.
"""

import logging
import smtplib
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr, formatdate, make_msgid
from typing import List, Optional, Dict, Any, Tuple
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction

from sage_imap.services.client import IMAPClient
from sage_imap.services.mailbox import IMAPMailboxService
from sage_imap.helpers.enums import DefaultMailboxes

logger = logging.getLogger(__name__)


class EmailSendingService:
    """
    Professional email sending service with Outlook-compatible standards.
    
    Features:
    - Auto-generated Message-ID following RFC standards
    - Proper email threading with In-Reply-To and References headers
    - Outlook-compatible email structure and headers
    - Priority handling
    - Rich HTML and plain text support
    - Attachment handling
    - Automatic saving to IMAP Sent folder
    - Comprehensive error handling and retry logic
    """
    
    def __init__(self, smtp_server=None):
        """
        Initialize the email sending service.
        
        Args:
            smtp_server: SMTPServer instance to use for sending
        """
        self.smtp_server = smtp_server
        self.logger = logger
    
    def send_email(
        self,
        to_addresses: List[str],
        subject: str,
        body_html: str = "",
        body_plain: str = "",
        cc_addresses: List[str] = None,
        bcc_addresses: List[str] = None,
        reply_to: str = "",
        priority: str = "normal",
        in_reply_to: str = "",
        references: str = "",
        attachments: List[Dict[str, Any]] = None,
        template=None,
        save_to_sent: bool = True,
        mailbox=None
    ) -> 'Email':
        """
        Send an email with professional standards.
        
        Args:
            to_addresses: List of recipient email addresses
            subject: Email subject
            body_html: HTML body content
            body_plain: Plain text body content
            cc_addresses: List of CC recipients
            bcc_addresses: List of BCC recipients
            reply_to: Reply-to address
            priority: Email priority (high, normal, low)
            in_reply_to: Message-ID being replied to
            references: References header for threading
            attachments: List of attachment dictionaries
            template: EmailTemplate instance used
            save_to_sent: Whether to save to IMAP Sent folder
            mailbox: Target mailbox (defaults to Sent folder)
            
        Returns:
            Email instance of the sent email
        """
        from sage_mailbox.models import Email
        
        # Validate inputs
        self._validate_send_parameters(to_addresses, subject, body_html, body_plain)
        
        # Prepare addresses
        cc_addresses = cc_addresses or []
        bcc_addresses = bcc_addresses or []
        attachments = attachments or []
        
        # Generate unique Message-ID
        message_id = self._generate_message_id()
        
        # Generate unique temporary UID (negative number based on timestamp)
        # This ensures uniqueness while being clearly identifiable as temporary
        import time
        temp_uid = -int(time.time() * 1000000)  # Negative microsecond timestamp
        
        # Create email record
        email = Email.objects.create(
            mailbox=mailbox or self._get_sent_mailbox(),
            uid=temp_uid,  # Temporary UID, will be updated after IMAP save
            message_id=message_id,
            subject=subject,
            from_address=self.smtp_server.from_email,
            from_name=self.smtp_server.from_name,
            to_addresses=to_addresses,
            cc_addresses=cc_addresses,
            bcc_addresses=bcc_addresses,
            reply_to=reply_to,
            priority=priority,
            plain_body=body_plain,
            html_body=body_html,
            in_reply_to=in_reply_to,
            references=references,
            smtp_server=self.smtp_server,
            template=template,
            is_outgoing=True,
            send_status='sending',
            date=timezone.now(),
            headers={}
        )
        
        try:
            # Create and send email message
            msg = self._create_email_message(
                email, to_addresses, cc_addresses, bcc_addresses, 
                attachments, message_id
            )
            
            # Send via SMTP
            self._send_smtp_message(msg, to_addresses + cc_addresses + bcc_addresses)
            
            # Save to IMAP Sent folder if requested
            if save_to_sent:
                self._save_to_sent_folder(email, msg)
            
            # Update email record
            email.send_status = 'sent'
            email.sent_at = timezone.now()
            email.save()
            
            self.logger.info(f"Successfully sent email '{subject}' to {len(to_addresses)} recipients")
            
            return email
            
        except Exception as e:
            # Update email record with error
            email.send_status = 'failed'
            email.send_attempts += 1
            email.send_error = str(e)
            email.save()
            
            self.logger.error(f"Failed to send email '{subject}': {e}")
            raise
    
    def _validate_send_parameters(self, to_addresses, subject, body_html, body_plain):
        """Validate email sending parameters."""
        if not to_addresses:
            raise ValidationError("At least one recipient is required")
        
        if not subject:
            raise ValidationError("Subject is required")
        
        if not body_html and not body_plain:
            raise ValidationError("Either HTML or plain text body is required")
        
        if not self.smtp_server:
            raise ValidationError("SMTP server is required")
        
        if not self.smtp_server.is_active:
            raise ValidationError("SMTP server is not active")
    
    def _generate_message_id(self) -> str:
        """
        Generate a unique Message-ID following RFC 5322 standards.
        
        Format: <unique-id@domain>
        Example: <20250117.123456.12345@example.com>
        """
        # Use timestamp and random component for uniqueness
        timestamp = datetime.now().strftime("%Y%m%d.%H%M%S")
        random_part = str(uuid.uuid4()).replace('-', '')[:8]
        
        # Extract domain from SMTP server or use default
        domain = self.smtp_server.from_email.split('@')[1] if '@' in self.smtp_server.from_email else 'localhost'
        
        return f"<{timestamp}.{random_part}@{domain}>"
    
    def _create_email_message(
        self, 
        email: 'Email', 
        to_addresses: List[str], 
        cc_addresses: List[str], 
        bcc_addresses: List[str], 
        attachments: List[Dict[str, Any]], 
        message_id: str
    ) -> MIMEMultipart:
        """Create a properly formatted email message."""
        
        # Create multipart message
        msg = MIMEMultipart('alternative')
        
        # Set basic headers
        msg['From'] = formataddr((email.from_name, email.from_address))
        msg['To'] = ', '.join(to_addresses)
        msg['Subject'] = email.subject
        msg['Date'] = formatdate(localtime=True)
        msg['Message-ID'] = message_id
        
        # Add CC if present
        if cc_addresses:
            msg['Cc'] = ', '.join(cc_addresses)
        
        # Add Reply-To if present
        if email.reply_to:
            msg['Reply-To'] = email.reply_to
        
        # Add threading headers
        if email.in_reply_to:
            msg['In-Reply-To'] = email.in_reply_to
        
        if email.references:
            msg['References'] = email.references
        
        # Add priority headers (Outlook-compatible)
        if email.priority == 'high':
            msg['X-Priority'] = '1'
            msg['X-MSMail-Priority'] = 'High'
            msg['Importance'] = 'High'
        elif email.priority == 'low':
            msg['X-Priority'] = '5'
            msg['X-MSMail-Priority'] = 'Low'
            msg['Importance'] = 'Low'
        else:
            msg['X-Priority'] = '3'
            msg['X-MSMail-Priority'] = 'Normal'
            msg['Importance'] = 'Normal'
        
        # Add User-Agent header
        msg['User-Agent'] = 'Django-Sage-Mailbox/1.0'
        
        # Add X-Mailer header for Outlook compatibility
        msg['X-Mailer'] = 'Django-Sage-Mailbox'
        
        # Add auto-generated signature if available
        plain_body = email.plain_body
        html_body = email.html_body
        
        if self.smtp_server.signature:
            signature_plain = f"\n\n--\n{self.smtp_server.signature}"
            signature_html = f'<br><br>--<br>{self.smtp_server.signature.replace(chr(10), "<br>")}'
            
            plain_body += signature_plain
            html_body += signature_html
        
        # Create text parts
        if plain_body:
            text_part = MIMEText(plain_body, 'plain', 'utf-8')
            msg.attach(text_part)
        
        if html_body:
            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(html_part)
        
        # Add attachments
        for attachment in attachments:
            self._add_attachment(msg, attachment)
        
        return msg
    
    def _add_attachment(self, msg: MIMEMultipart, attachment: Dict[str, Any]):
        """Add an attachment to the email message."""
        try:
            # Handle different attachment formats
            if 'file_path' in attachment:
                with open(attachment['file_path'], 'rb') as f:
                    content = f.read()
                filename = attachment.get('filename', attachment['file_path'].split('/')[-1])
            elif 'content' in attachment:
                content = attachment['content']
                filename = attachment.get('filename', 'attachment')
            else:
                self.logger.warning(f"Invalid attachment format: {attachment}")
                return
            
            # Create attachment part
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(content)
            encoders.encode_base64(part)
            
            # Add headers
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {filename}'
            )
            
            msg.attach(part)
            
        except Exception as e:
            self.logger.error(f"Failed to add attachment {attachment}: {e}")
    
    def _send_smtp_message(self, msg: MIMEMultipart, all_recipients: List[str]):
        """Send the email message via SMTP."""
        try:
            # Create SMTP connection
            if self.smtp_server.use_ssl:
                server = smtplib.SMTP_SSL(
                    self.smtp_server.host, 
                    self.smtp_server.port,
                    timeout=self.smtp_server.timeout
                )
            else:
                server = smtplib.SMTP(
                    self.smtp_server.host, 
                    self.smtp_server.port,
                    timeout=self.smtp_server.timeout
                )
                
                if self.smtp_server.use_tls:
                    server.starttls()
            
            # Authenticate
            if self.smtp_server.username and self.smtp_server.password:
                server.login(
                    self.smtp_server.username,
                    self.smtp_server.get_decrypted_password()
                )
            
            # Send message
            server.send_message(msg, to_addrs=all_recipients)
            server.quit()
            
            self.logger.debug(f"Successfully sent email via SMTP to {len(all_recipients)} recipients")
            
        except Exception as e:
            self.logger.error(f"SMTP sending failed: {e}")
            raise
    
    def _save_to_sent_folder(self, email: 'Email', msg: MIMEMultipart):
        """Save the sent email to the IMAP Sent folder."""
        try:
            # Find the corresponding IMAP server for this SMTP server
            imap_server = self._get_imap_server_for_smtp()
            
            if not imap_server:
                self.logger.warning("No IMAP server found for saving to Sent folder")
                return
            
            # Create IMAP connection
            from sage_imap.services.client import ConnectionConfig
            
            config = ConnectionConfig(
                host=imap_server.host,
                username=imap_server.username,
                password=imap_server.get_decrypted_password(),
                port=imap_server.port,
                use_ssl=imap_server.use_ssl,
                timeout=imap_server.timeout,
            )
            
            with IMAPClient.from_config(config) as client:
                mailbox_service = IMAPMailboxService(client)
                
                # Find or create Sent folder
                sent_folder = self._find_sent_folder(imap_server)
                
                # Select Sent folder
                select_result = mailbox_service.select(sent_folder.name)
                if not select_result.success:
                    self.logger.error(f"Failed to select Sent folder: {select_result.error_message}")
                    return
                
                # Upload email to Sent folder
                raw_message = msg.as_string().encode('utf-8')
                upload_result = mailbox_service.append(
                    sent_folder.name,
                    raw_message,
                    ['\\Seen']  # Mark as seen
                )
                
                if upload_result.success:
                    self.logger.info(f"Successfully saved email to Sent folder")
                    
                    # Update email record with the new UID if available
                    if hasattr(upload_result, 'uid'):
                        email.uid = upload_result.uid
                        email.save()
                else:
                    self.logger.error(f"Failed to save to Sent folder: {upload_result.error_message}")
                    
        except Exception as e:
            self.logger.error(f"Failed to save to Sent folder: {e}")
    
    def _get_imap_server_for_smtp(self):
        """Get the corresponding IMAP server for this SMTP server."""
        from sage_mailbox.models import IMAPServer
        
        # Try to find IMAP server by matching email domain or username
        try:
            # First try exact username match
            return IMAPServer.objects.filter(
                username=self.smtp_server.username,
                owner=self.smtp_server.owner,
                is_active=True
            ).first()
        except Exception:
            pass
        
        # Try to find by email domain
        try:
            domain = self.smtp_server.from_email.split('@')[1]
            return IMAPServer.objects.filter(
                host__icontains=domain,
                owner=self.smtp_server.owner,
                is_active=True
            ).first()
        except Exception:
            pass
        
        # Return first active IMAP server for this user
        return IMAPServer.objects.filter(
            owner=self.smtp_server.owner,
            is_active=True
        ).first()
    
    def _find_sent_folder(self, imap_server):
        """Find or create the Sent folder."""
        from sage_mailbox.models import Mailbox
        
        # Try to find existing Sent folder
        sent_folder = Mailbox.objects.filter(
            server=imap_server,
            name__in=['Sent', 'SENT', 'Sent Items', 'Sent Messages']
        ).first()
        
        if not sent_folder:
            # Create default Sent folder
            sent_folder = Mailbox.objects.create(
                server=imap_server,
                name='Sent',
                display_name='Sent',
                is_default=True
            )
        
        return sent_folder
    
    def _get_sent_mailbox(self):
        """Get the default Sent mailbox for this SMTP server."""
        imap_server = self._get_imap_server_for_smtp()
        
        if imap_server:
            return self._find_sent_folder(imap_server)
        
        # If no IMAP server found, return None (will be handled later)
        return None
    
    def create_reply(self, original_email: 'Email', reply_body_html: str = "", reply_body_plain: str = "") -> 'Email':
        """
        Create a reply email with proper threading headers.
        
        Args:
            original_email: The email being replied to
            reply_body_html: HTML body of the reply
            reply_body_plain: Plain text body of the reply
            
        Returns:
            Email instance for the reply (not yet sent)
        """
        from sage_mailbox.models import Email
        
        # Create reply subject
        subject = original_email.subject
        if not subject.lower().startswith('re:'):
            subject = f"Re: {subject}"
        
        # Create References header for threading
        references = original_email.references or ""
        if original_email.message_id:
            if references:
                references += f" {original_email.message_id}"
            else:
                references = original_email.message_id
        
        # Create reply email record
        import time
        temp_uid = -int(time.time() * 1000000)  # Negative microsecond timestamp
        
        reply_email = Email.objects.create(
            mailbox=self._get_sent_mailbox(),
            uid=temp_uid,
            message_id=self._generate_message_id(),
            subject=subject,
            from_address=self.smtp_server.from_email,
            from_name=self.smtp_server.from_name,
            to_addresses=[original_email.from_address],
            cc_addresses=[],
            bcc_addresses=[],
            reply_to=self.smtp_server.from_email,
            priority='normal',
            plain_body=reply_body_plain,
            html_body=reply_body_html,
            in_reply_to=original_email.message_id,
            references=references,
            smtp_server=self.smtp_server,
            is_outgoing=True,
            send_status='draft',
            date=timezone.now(),
            headers={}
        )
        
        return reply_email
    
    def create_forward(self, original_email: 'Email', forward_body_html: str = "", forward_body_plain: str = "") -> 'Email':
        """
        Create a forward email with original email content.
        
        Args:
            original_email: The email being forwarded
            forward_body_html: HTML body to prepend to the forward
            forward_body_plain: Plain text body to prepend to the forward
            
        Returns:
            Email instance for the forward (not yet sent)
        """
        from sage_mailbox.models import Email
        
        # Create forward subject
        subject = original_email.subject
        if not subject.lower().startswith('fwd:') and not subject.lower().startswith('fw:'):
            subject = f"Fwd: {subject}"
        
        # Create forward body with original email content
        original_date = original_email.date.strftime("%Y-%m-%d %H:%M:%S") if original_email.date else "Unknown"
        
        forward_header_plain = f"\n\n---------- Forwarded message ----------\n"
        forward_header_plain += f"From: {original_email.from_name} <{original_email.from_address}>\n"
        forward_header_plain += f"Date: {original_date}\n"
        forward_header_plain += f"Subject: {original_email.subject}\n"
        forward_header_plain += f"To: {', '.join(original_email.to_addresses)}\n\n"
        
        forward_header_html = f"<br><br>---------- Forwarded message ----------<br>"
        forward_header_html += f"<b>From:</b> {original_email.from_name} &lt;{original_email.from_address}&gt;<br>"
        forward_header_html += f"<b>Date:</b> {original_date}<br>"
        forward_header_html += f"<b>Subject:</b> {original_email.subject}<br>"
        forward_header_html += f"<b>To:</b> {', '.join(original_email.to_addresses)}<br><br>"
        
        # Combine forward body with original content
        combined_plain = forward_body_plain + forward_header_plain + original_email.plain_body
        combined_html = forward_body_html + forward_header_html + original_email.html_body
        
        # Create forward email record
        import time
        temp_uid = -int(time.time() * 1000000)  # Negative microsecond timestamp
        
        forward_email = Email.objects.create(
            mailbox=self._get_sent_mailbox(),
            uid=temp_uid,
            message_id=self._generate_message_id(),
            subject=subject,
            from_address=self.smtp_server.from_email,
            from_name=self.smtp_server.from_name,
            to_addresses=[],
            cc_addresses=[],
            bcc_addresses=[],
            reply_to=self.smtp_server.from_email,
            priority='normal',
            plain_body=combined_plain,
            html_body=combined_html,
            smtp_server=self.smtp_server,
            is_outgoing=True,
            send_status='draft',
            date=timezone.now(),
            headers={}
        )
        
        return forward_email 