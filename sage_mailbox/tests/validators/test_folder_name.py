import pytest

from django.core.exceptions import ValidationError

from sage_mailbox.validators import FolderNameValidator


class TestFolderNameValidator:

    def setup_method(self):
        self.validator = FolderNameValidator()

    @pytest.mark.parametrize("folder_name", [
        "MyFolder",           # letters
        "Folder123",          # letters and numbers
        "Folder-Name_123",    # hyphen and underscore
        "Folder.Name",        # dot in name
        "A" * 255             # exactly 255 characters
    ])
    def test_valid_folder_names(self, folder_name):
        # These should pass validation
        result = self.validator(folder_name)
        assert result is None

    @pytest.mark.parametrize("folder_name", [
        "",                          # Empty string
        "A" * 256,                   # Exceeds 255 characters
    ])
    def test_invalid_folder_names_length(self, folder_name):
        with pytest.raises(ValidationError) as exc_info:
            self.validator(folder_name)
        assert exc_info.value.messages[0] == "Folder name must be between 1 and 255 characters long."

    @pytest.mark.parametrize("folder_name", [
        "Invalid@Folder",            # Invalid special characters
        "Folder#Name",               # Invalid special character
        "Folder Name With Spaces",   # Spaces in name
        "-Invalid",                  # Starts with invalid character
        "Invalid-"                   # Ends with invalid character
    ])
    def test_invalid_folder_names_characters(self, folder_name):
        with pytest.raises(ValidationError) as exc_info:
            self.validator(folder_name)
        assert exc_info.value.messages[0] == "Folder name contains invalid characters. Allowed characters are letters, numbers, underscore, hyphen, and dot. Spaces are not allowed."

    @pytest.mark.parametrize("folder_name", [
        "A",                         # Exactly 1 character
        "A" * 255                    # Exactly 255 characters
    ])
    def test_edge_cases(self, folder_name):
        # Edge case for exactly 1 and 255 characters, should pass validation
        result = self.validator(folder_name)
        assert result is None
