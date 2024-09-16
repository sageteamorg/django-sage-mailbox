from django.db import models
from django.db.models import BooleanField, Case, Count, Value, When
from django.db.models.functions import Length


class EmailMessageQuerySet(models.QuerySet):
    def total_attachments(self):
        return self.annotate(total_attachments=Count("attachments__id"))

    def has_attachments(self):
        return self.annotate(
            has_attachments=Case(
                When(attachments__isnull=False, then=True),
                default=False,
                output_field=BooleanField(),
            )
        )

    def select_related_mailbox(self):
        return self.select_related("mailbox")

    def list_attachments(self):
        return self.prefetch_related("attachments")

    def unread(self):
        return self.filter(is_read=False)

    def flagged(self):
        return self.filter(is_flagged=True)

    # def has_cc(self):
    #     return self.annotate(
    #         has_cc=Case(
    #             When(Length("cc_address") > 0, then=Value(True)),
    #             default=Value(False),
    #             output_field=BooleanField(),
    #         )
    #     )

    # def has_bcc(self):
    #     return self.annotate(
    #         has_bcc=Case(
    #             When(Length("bcc_address") > 0, then=Value(True)),
    #             default=Value(False),
    #             output_field=BooleanField(),
    #         )
    #     )
