import pytest
from django.utils import timezone
from model_bakery import baker
from datetime import datetime
from sage_mailbox.models import EmailMessage, Flag, Mailbox
from autoslug import AutoSlugField
from django.db.models import F


# Register the custom generator for AutoSlugField
def slug_generator():
    return 'test-slug'

baker.generators.add(AutoSlugField, slug_generator)


@pytest.mark.django_db
class TestEmailMessageQuerySet:
    
    def test_total_attachments(self):
        """Test total attachment count for each email."""
        email = baker.make(EmailMessage, _quantity=3)
        attachment = baker.make('sage_mailbox.Attachment', email_message=email[0], _quantity=5)
        attachment2 = baker.make('sage_mailbox.Attachment', email_message=email[1], _quantity=2)

        queryset = EmailMessage.objects.total_attachments()

        assert queryset.get(id=email[0].id).total_attachments == 5
        assert queryset.get(id=email[1].id).total_attachments == 2
        assert queryset.get(id=email[2].id).total_attachments == 0

    def test_has_attachments(self):
        """Test annotation to check if emails have attachments."""
        email = baker.make(EmailMessage, _quantity=3)
        baker.make('sage_mailbox.Attachment', email_message=email[0])

        queryset = EmailMessage.objects.has_attachments()
        assert queryset.get(id=email[0].id).has_attachments is True
        assert queryset.get(id=email[1].id).has_attachments is False

    def test_select_related_mailbox(self, django_assert_num_queries):
        """Test select_related optimization for mailbox."""
        mailbox = baker.make(Mailbox)
        email = baker.make(EmailMessage, mailbox=mailbox)

        # Ensure that select_related is optimizing the query by fetching related objects in one query
        with django_assert_num_queries(1):  # One query should fetch both EmailMessage and Mailbox
            result_email = EmailMessage.objects.select_related_mailbox().get(id=email.id)
            assert result_email.mailbox == mailbox  # Access the mailbox without triggering another query

    def test_list_attachments(self):
        """Test prefetching attachments."""
        email = baker.make(EmailMessage)
        baker.make('sage_mailbox.Attachment', email_message=email, _quantity=3)
        queryset = EmailMessage.objects.list_attachments()

        assert queryset.count() == 1
        assert queryset[0].attachments.count() == 3

    def test_unread(self):
        """Test filtering unread emails."""
        baker.make(EmailMessage, is_read=False, _quantity=2)
        baker.make(EmailMessage, is_read=True, _quantity=2)

        assert EmailMessage.objects.unread().count() == 2

    def test_flagged(self):
        """Test filtering flagged emails."""
        baker.make(EmailMessage, is_flagged=True, _quantity=3)
        baker.make(EmailMessage, is_flagged=False, _quantity=2)

        assert EmailMessage.objects.flagged().count() == 3


@pytest.mark.django_db
class TestEmailMessageManager:
    
    def test_total_attachments_manager(self):
        """Test total attachments through manager."""
        email = baker.make(EmailMessage)
        baker.make('sage_mailbox.Attachment', email_message=email, _quantity=2)

        queryset = EmailMessage.objects.total_attachments()
        assert queryset.get(id=email.id).total_attachments == 2

    def test_has_attachments_manager(self):
        """Test has_attachments through manager."""
        email = baker.make(EmailMessage)
        baker.make('sage_mailbox.Attachment', email_message=email)

        queryset = EmailMessage.objects.has_attachments()
        assert queryset.get(id=email.id).has_attachments is True

    def test_unread_manager(self):
        """Test unread emails through manager."""
        baker.make(EmailMessage, is_read=False)
        assert EmailMessage.objects.unread().count() == 1

    def test_flagged_manager(self):
        """Test flagged emails through manager."""
        baker.make(EmailMessage, is_flagged=True)
        assert EmailMessage.objects.flagged().count() == 1
