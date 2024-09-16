import imaplib
import logging

from django.conf import settings
from django.core.checks import Error, Warning, register

from sage_mailbox.conf import imap_settings
from sage_mailbox.exc import (
    IMAPAuthenticationError,
    IMAPConfigurationError,
    IMAPConnectionError,
    IMAPUnexpectedError,
)

logger = logging.getLogger(__name__)


@register()
def check_imap_config(app_configs, **kwargs):
    """
    Check the IMAP configuration and other required settings for the application.

    This function verifies that all required IMAP settings, Django apps, and certain
    settings are present. It also attempts to establish a connection to the IMAP server
    to ensure the settings are correct. Any errors encountered during these checks
    are returned.

    Parameters
    ----------
    app_configs : dict
        The application configurations.
    **kwargs
        Additional keyword arguments.

    Returns
    -------
    list of Error or Warning
        A list of Error or Warning objects representing any configuration or connection
        errors found.

    Raises
    ------
    IMAPConfigurationError
        If any required IMAP configuration settings are missing.
    IMAPAuthenticationError
        If the authentication with the IMAP server fails.
    IMAPConnectionError
        If there is a connection error with the IMAP server.
    IMAPUnexpectedError
        If an unexpected error occurs during the IMAP configuration check.

    Examples
    --------
    >>> errors = check_imap_config(app_configs)
    >>> if errors:
    ...     for error in errors:
    ...         print(error)
    """
    errors = []

    # Check that required apps are installed
    required_apps = ["django.contrib.sites", "django_jsonform"]
    for app in required_apps:
        if app not in settings.INSTALLED_APPS:
            errors.append(
                Error(
                    f"The required app '{app}' is not installed.",
                    id="sage_integration.E001",
                )
            )

    # Check that SITE_ID is set
    if not hasattr(settings, "SITE_ID"):
        errors.append(
            Error(
                "SITE_ID is not set in settings.",
                id="sage_integration.E002",
            )
        )
    elif not isinstance(settings.SITE_ID, int):
        errors.append(
            Error(
                "SITE_ID must be an integer.",
                id="sage_integration.E003",
            )
        )

    # Check that upload-related settings are set
    upload_settings = ["MEDIA_URL", "MEDIA_ROOT", "FILE_UPLOAD_HANDLERS"]
    for setting in upload_settings:
        if not hasattr(settings, setting):
            errors.append(
                Error(
                    f"The required setting '{setting}' is not set.",
                    id="sage_integration.E008",
                )
            )

    # Function to get IMAP settings
    def get_imap_settings():
        return {
            "IMAP_SERVER_DOMAIN": imap_settings.IMAP_SERVER_DOMAIN,
            "IMAP_SERVER_PORT": imap_settings.IMAP_SERVER_PORT,
            "IMAP_SERVER_USER": imap_settings.IMAP_SERVER_USER,
            "IMAP_SERVER_PASSWORD": imap_settings.IMAP_SERVER_PASSWORD,
        }

    # Function to check missing configurations
    def check_missing_configs(settings):
        missing = [key for key, value in settings.items() if not value]
        if missing:
            raise IMAPConfigurationError(
                f"IMAP configuration settings are missing: {', '.join(missing)}."
            )

    # Check IMAP configuration settings
    try:
        imap_settings_dict = get_imap_settings()
        check_missing_configs(imap_settings_dict)
    except IMAPConfigurationError as e:
        errors.append(
            Error(
                str(e),
                id="sage_integration.E004",
            )
        )

    # Check IMAP connection
    try:
        mail = imaplib.IMAP4_SSL(
            imap_settings_dict["IMAP_SERVER_DOMAIN"],
            imap_settings_dict["IMAP_SERVER_PORT"],
        )
        mail.login(
            imap_settings_dict["IMAP_SERVER_USER"],
            imap_settings_dict["IMAP_SERVER_PASSWORD"],
        )
        mail.logout()
    except imaplib.IMAP4.error as e:
        if "authentication failed" in str(e).lower():
            errors.append(
                Error(
                    str(IMAPAuthenticationError()),
                    id="sage_integration.E007",
                )
            )
        else:
            errors.append(
                Error(
                    str(IMAPConnectionError(detail=str(e))),
                    id="sage_integration.E005",
                )
            )
    except Exception as e:
        errors.append(
            Error(
                str(IMAPUnexpectedError(detail=str(e))),
                id="sage_integration.E006",
            )
        )

    return errors
