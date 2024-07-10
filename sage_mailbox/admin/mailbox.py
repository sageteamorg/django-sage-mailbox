from typing import Any

from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _
from sage_imap.exceptions import (
    IMAPFolderExistsError,
    IMAPFolderNotFoundError,
    IMAPFolderOperationError,
    IMAPUnexpectedError,
)
from sage_imap.helpers.mailbox import DefaultMailboxes
from sage_imap.services import IMAPClient, IMAPFolderService

from sage_mailbox.models import Mailbox


@admin.register(Mailbox)
class MailboxAdmin(admin.ModelAdmin):
    change_list_template = "admin/mailbox/change_list.html"

    list_display = ("name", "slug", "created_at", "modified_at")
    search_fields = ("name",)
    ordering = ("name",)
    list_per_page = 25
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ("created_at", "modified_at")
    fieldsets = (
        (None, {"fields": ("name", "slug")}),
        (_("Change Log"), {"fields": ("created_at", "modified_at")}),
    )
    readonly_fields = ("created_at", "modified_at")

    def save_model(self, request, obj, form, change):
        old_name = None
        new_name = form.cleaned_data.get("name")

        if change:
            old_name = Mailbox.objects.get(pk=obj.pk).name

            if old_name in DefaultMailboxes._value2member_map_:
                self.message_user(
                    request,
                    _("You do not have permission to rename a default mailbox."),
                    messages.ERROR,
                )
                raise PermissionDenied(
                    "You do not have permission to rename a default mailbox."
                )

        with IMAPClient(
            settings.IMAP_SERVER_DOMAIN,
            settings.IMAP_SERVER_USER,
            settings.IMAP_SERVER_PASSWORD,
        ) as client:
            service = IMAPFolderService(client)
            try:
                super().save_model(request, obj, form, change)
                if change and old_name and old_name != new_name:
                    service.rename_folder(old_name, new_name)
                    self.message_user(
                        request,
                        _("The folder was successfully renamed on the IMAP server."),
                        messages.SUCCESS,
                    )
                elif not change:
                    service.create_folder(new_name)
                    self.message_user(
                        request,
                        _("The folder was successfully created on the IMAP server."),
                        messages.SUCCESS,
                    )
            except IMAPFolderExistsError:
                self.message_user(
                    request,
                    _("The folder already exists on the IMAP server."),
                    messages.WARNING,
                )
            except IMAPFolderNotFoundError:
                self.message_user(
                    request,
                    _("The folder to be renamed was not found on the IMAP server."),
                    messages.ERROR,
                )
            except IMAPFolderOperationError as e:
                self.message_user(
                    request,
                    _(
                        "An error occurred while performing the operation on the IMAP server: %s"
                    )
                    % str(e),
                    messages.ERROR,
                )
            except IMAPUnexpectedError as e:
                self.message_user(
                    request,
                    _("An unexpected IMAP error occurred: %s") % str(e),
                    messages.ERROR,
                )
            except Exception as e:
                self.message_user(
                    request,
                    _("An unexpected error occurred: %s") % str(e),
                    messages.ERROR,
                )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("sync-mailboxes/", self.sync_mailboxes, name="sync-mailboxes"),
        ]
        return custom_urls + urls

    def sync_mailboxes(self, request):
        with IMAPClient(
            settings.IMAP_SERVER_DOMAIN,
            settings.IMAP_SERVER_USER,
            settings.IMAP_SERVER_PASSWORD,
        ) as client:
            service = IMAPFolderService(client)
            try:
                folders = service.list_folders()
                existing_mailboxes = set(Mailbox.objects.values_list("name", flat=True))
                existing_mailboxes_lower = {mailbox for mailbox in existing_mailboxes}
                new_mailboxes = {
                    folder for folder in folders
                } - existing_mailboxes_lower
                for folder in new_mailboxes:
                    Mailbox.objects.create(name=folder)
                self.message_user(
                    request,
                    _("Mailboxes successfully synced with IMAP server."),
                    messages.SUCCESS,
                )
            except IMAPFolderOperationError:
                self.message_user(
                    request,
                    _(
                        "An error occurred while syncing the mailboxes with the IMAP server."
                    ),
                    messages.ERROR,
                )
            except Exception as e:
                self.message_user(
                    request,
                    _("An unexpected error occurred: %s") % str(e),
                    messages.ERROR,
                )
        return HttpResponseRedirect(reverse("admin:sage_mailbox_mailbox_changelist"))

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except PermissionDenied:
            return HttpResponseRedirect(
                reverse("admin:sage_mailbox_mailbox_changelist")
            )

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet) -> None:
        with IMAPClient(
            settings.IMAP_SERVER_DOMAIN,
            settings.IMAP_SERVER_USER,
            settings.IMAP_SERVER_PASSWORD,
        ) as client:
            service = IMAPFolderService(client)
            for obj in queryset:
                if obj.name in DefaultMailboxes._value2member_map_:
                    self.message_user(
                        request,
                        _("Cannot delete default mailbox: %s") % obj.name,
                        messages.ERROR,
                    )
                    continue
                try:
                    service.delete_folder(obj.name)
                    obj.delete()
                    self.message_user(
                        request,
                        _("Successfully deleted mailbox: %s from IMAP Server.")
                        % obj.name,
                        messages.SUCCESS,
                    )
                except (
                    IMAPFolderNotFoundError,
                    IMAPFolderOperationError,
                    IMAPUnexpectedError,
                ) as e:
                    self.message_user(
                        request,
                        _(
                            "An error occurred while deleting the mailbox '%s' on the IMAP server: %s"
                        )
                        % (obj.name, str(e)),
                        messages.ERROR,
                    )

    def delete_model(self, request: HttpRequest, obj: Any) -> None:
        if obj.name in DefaultMailboxes._value2member_map_:
            self.message_user(
                request,
                _("Cannot delete default mailbox: %s") % obj.name,
                messages.ERROR,
            )
            raise PermissionDenied("Cannot delete default mailbox.")
        with IMAPClient(
            settings.IMAP_SERVER_DOMAIN,
            settings.IMAP_SERVER_USER,
            settings.IMAP_SERVER_PASSWORD,
        ) as client:
            service = IMAPFolderService(client)
            try:
                service.delete_folder(obj.name)
                super().delete_model(request, obj)
                self.message_user(
                    request,
                    _("Successfully deleted mailbox: %s") % obj.name,
                    messages.SUCCESS,
                )
            except (
                IMAPFolderNotFoundError,
                IMAPFolderOperationError,
                IMAPUnexpectedError,
            ) as e:
                self.message_user(
                    request,
                    _(
                        "An error occurred while deleting the mailbox '%s' on the IMAP server: %s"
                    )
                    % (obj.name, str(e)),
                    messages.ERROR,
                )
                raise PermissionDenied("Error deleting mailbox on IMAP server.")
