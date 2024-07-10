from django.db import models
from django.utils.translation import gettext_lazy as _


class TimestampMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    modified_at = models.DateTimeField(auto_now=True, verbose_name=_("Modified At"))

    class Meta:
        abstract = True
