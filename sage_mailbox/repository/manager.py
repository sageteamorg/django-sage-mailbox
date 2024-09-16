from django.db import models

from sage_mailbox.repository.queryset import EmailMessageQuerySet


class EmailMessageManager(models.Manager):
    def get_queryset(self):
        return EmailMessageQuerySet(self.model, using=self._db)

    def total_attachments(self):
        return self.get_queryset().total_attachments()

    def has_attachments(self):
        return self.get_queryset().has_attachments()

    def select_related_mailbox(self):
        return self.get_queryset().select_related_mailbox()

    def list_attachments(self):
        return self.get_queryset().list_attachments()

    def unread(self):
        return self.get_queryset().unread()

    def flagged(self):
        return self.get_queryset().flagged()

    # def has_cc(self):
    #     return self.get_queryset().has_cc()

    # def has_bcc(self):
    #     return self.get_queryset().has_bcc()
