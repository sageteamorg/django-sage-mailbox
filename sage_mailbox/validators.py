import re

from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _


@deconstructible
class FolderNameValidator:
    """
    Validator for folder names.

    Rules:
    - Length must be between 1 and 255 characters.
    - No special characters except underscore and hyphen.
    - No spaces allowed.
    - Must be unique (this will be handled by the unique constraint on the field).
    """

    length_error_message = "Folder name must be between 1 and 255 characters long."
    character_error_message = "Folder name contains invalid characters. Allowed characters are letters, numbers, underscore, and hyphen. Spaces are not allowed."
    code_length = "folder_name_length"
    code_character = "folder_name_invalid_character"
    regex = re.compile(r"^[\w-]+$")

    def __call__(self, value):
        if not (1 <= len(value) <= 255):
            raise ValidationError(self.length_error_message, code=self.code_length)

        if not self.regex.match(value):
            raise ValidationError(
                self.character_error_message, code=self.code_character
            )

    def __eq__(self, other):
        return (
            isinstance(other, FolderNameValidator)
            and self.length_error_message == other.length_error_message
            and self.character_error_message == other.character_error_message
            and self.code_length == other.code_length
            and self.code_character == other.code_character
            and self.regex.pattern == other.regex.pattern
        )


validate_folder_name = FolderNameValidator()


@deconstructible
class CommaSeparatedEmailValidator:
    message = _("'{email}' is not a valid email address.")
    code = "invalid_comma_separated_email"

    def __init__(self, message=None, code=None):
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code

    def __call__(self, value):
        emails = value.split(",")
        for email in emails:
            email = email.strip()
            if email:
                try:
                    validate_email(email)
                except ValidationError:
                    raise ValidationError(
                        self.message.format(email=email),
                        code=self.code,
                        params={"email": email},
                    )

    def __eq__(self, other):
        return (
            isinstance(other, CommaSeparatedEmailValidator)
            and self.message == other.message
            and self.code == other.code
        )


validate_comma_separated_email = CommaSeparatedEmailValidator()
