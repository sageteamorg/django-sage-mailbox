from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SageMailboxConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sage_mailbox"
    verbose_name = _("Mailbox")

    def ready(self):
        from . import checks
