from typing import Any

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.models import LogEntry
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponseRedirect
from django.http.response import HttpResponse
from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _
from sage_imap.exceptions import (
    IMAPFolderExistsError,
    IMAPFolderNotFoundError,
    IMAPFolderOperationError,
)
from sage_imap.services import IMAPClient, IMAPFolderService

from sage_mailbox.admin.actions import delete_selected
from sage_mailbox.models.mailbox import Mailbox, StandardMailboxNames

# IMAP configuration
imap_host = getattr(settings, "IMAP_SERVER_DOMAIN", None)
imap_username = getattr(settings, "IMAP_SERVER_USER", None)
imap_password = getattr(settings, "IMAP_SERVER_PASSWORD", None)


@admin.register(Mailbox)
class MailboxAdmin(admin.ModelAdmin):
    change_list_template = "admin/mailbox/change_list.html"
    list_display = ("name", "slug", "folder_type", "created_at", "modified_at")
    search_fields = ("name",)
    ordering = ("name",)
    list_per_page = 25
    list_filter = ("folder_type", "created_at", "modified_at")
    fieldsets = (
        (None, {"fields": ("name", "slug", "folder_type")}),
        (_("Change Log"), {"fields": ("created_at", "modified_at")}),
    )
    readonly_fields = ("created_at", "modified_at", "slug")
    actions = [delete_selected]

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            if obj.folder_type != StandardMailboxNames.CUSTOM:
                return self.readonly_fields + ("name",)
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        new_name = form.cleaned_data.get("name")

        try:
            with transaction.atomic():
                with IMAPClient(imap_host, imap_username, imap_password) as client:
                    folder_service = IMAPFolderService(client)
                    if change:
                        old_name = Mailbox.objects.get(pk=obj.pk).name
                        if old_name != new_name:
                            try:
                                folder_service.rename_folder(old_name, new_name)
                            except IMAPFolderNotFoundError:
                                raise ValidationError(
                                    _("The folder to be renamed does not exist.")
                                )
                            except IMAPFolderOperationError as e:
                                raise ValidationError(str(e))
                    else:
                        try:
                            folder_service.create_folder(new_name)
                        except IMAPFolderExistsError:
                            raise ValidationError(
                                _("A folder with this name already exists.")
                            )
                        except IMAPFolderOperationError as e:
                            raise ValidationError(str(e))
                    super().save_model(request, obj, form, change)
                messages.success(
                    request, f'The Mailbox "{new_name}" was added successfully.'
                )
        except ValidationError as e:
            messages.error(request, f"Error: {e.message}")
        except Exception as e:
            messages.error(request, f"Unexpected error: {str(e)}")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "sync-folders/",
                self.admin_site.admin_view(self.sync_folders),
                name="sync_folders",
            )
        ]
        return custom_urls + urls

    def delete_model(self, request, obj):
        try:
            with transaction.atomic():
                with IMAPClient(imap_host, imap_username, imap_password) as client:
                    folder_service = IMAPFolderService(client)
                    try:
                        folder_service.delete_folder(obj.name)
                    except IMAPFolderNotFoundError:
                        super().delete_model(request, obj)
                        messages.warning(
                            request,
                            f'The Mailbox "{obj.name}" was deleted from admin, '
                            "but it did not exist on the IMAP server.",
                        )
                    except IMAPFolderOperationError as e:
                        raise ValidationError(str(e))
                    else:
                        super().delete_model(request, obj)
                        messages.success(
                            request,
                            f'The Mailbox "{obj.name}" was deleted successfully '
                            "from both admin and IMAP server.",
                        )
        except ValidationError as e:
            messages.error(request, f"Error: {e.message}")
        except Exception as e:
            messages.error(request, f"Unexpected error: {str(e)}")

    def delete_queryset(self, request, queryset):
        try:
            with transaction.atomic():
                with IMAPClient(imap_host, imap_username, imap_password) as client:
                    folder_service = IMAPFolderService(client)
                    for obj in queryset:
                        try:
                            folder_service.delete_folder(obj.name)
                        except IMAPFolderNotFoundError:
                            super().delete_model(request, obj)
                            messages.warning(
                                request,
                                f'The mailbox "{obj.name}" was deleted from admin, '
                                "but it did not exist on the IMAP server.",
                            )
                        except IMAPFolderOperationError as e:
                            raise ValidationError(str(e))
                        else:
                            super().delete_model(request, obj)
                    super().delete_queryset(request, queryset)
                messages.success(
                    request,
                    "The selected Mailboxes were deleted successfully "
                    "from both admin and IMAP server.",
                )
        except ValidationError as e:
            messages.error(request, f"Error: {e.message}")
        except Exception as e:
            messages.error(request, f"Unexpected error: {str(e)}")

    def response_add(self, request, obj, post_url_continue=None):
        """
        Handles the HTTP response after adding a new object in the Django admin.

        This method is overridden to prevent the double flash message issue
        that can occur in Django's admin interface.
        """
        if "_continue" in request.POST:
            return super().response_add(request, obj, post_url_continue)
        elif "_addanother" in request.POST:
            return HttpResponseRedirect(request.path)
        elif "_save" in request.POST:
            post_url = reverse(
                "admin:{}_{}_changelist".format(
                    self.opts.app_label, self.opts.model_name
                ),
                current_app=self.admin_site.name,
            )
            return HttpResponseRedirect(post_url)
        return HttpResponseRedirect(self.get_success_url(request, obj))

    def response_change(self, request, obj):
        """
        Handles the HTTP response after changing an existing object in the Django
        admin.

        Similar to `response_add`, this method prevents the issue of double flash messages.
        """
        if "_continue" in request.POST:
            return super().response_change(request, obj)
        elif "_saveasnew" in request.POST:
            return super().response_add(request, obj)
        elif "_addanother" in request.POST:
            return HttpResponseRedirect(request.path)
        elif "_save" in request.POST:
            post_url = reverse(
                "admin:{}_{}_changelist".format(
                    self.opts.app_label, self.opts.model_name
                ),
                current_app=self.admin_site.name,
            )
            return HttpResponseRedirect(post_url)
        return HttpResponseRedirect(self.get_success_url(request, obj))

    def response_delete(
        self, request: HttpRequest, obj_display: str, obj_id: int
    ) -> HttpResponse:
        post_url = reverse(
            "admin:{}_{}_changelist".format(self.opts.app_label, self.opts.model_name),
            current_app=self.admin_site.name,
        )
        return HttpResponseRedirect(post_url)

    def get_success_url(self, request, obj):
        return request.META.get("HTTP_REFERER", "/admin/")

    def sync_folders(self, request):
        """Synchronizes the mailboxes between the IMAP server and the Django admin."""
        try:
            with IMAPClient(imap_host, imap_username, imap_password) as client:
                folder_service = IMAPFolderService(client)
                folders = folder_service.list_folders()
                for folder_name in folders:
                    Mailbox.objects.update_or_create(
                        name=folder_name, defaults={"slug": folder_name.lower()}
                    )
                messages.success(request, "Mailboxes synchronized successfully.")
        except Exception as e:
            messages.error(request, f"Unexpected error: {str(e)}")
        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/admin/"))

    def log_deletion(
        self, request: HttpRequest, obj: Any, object_repr: str
    ) -> LogEntry:
        return super().log_deletion(request, obj, object_repr)
