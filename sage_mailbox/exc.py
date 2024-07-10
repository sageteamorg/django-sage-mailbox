import uuid


class SageError(Exception):
    """Base class for all Sage exceptions.

    Attributes:
        status_code (int): HTTP status code associated with the error.
        default_detail (str): Default error message.
        default_code (str): Default error code.
        section_code (str): Section code for categorizing errors.
        detail (str): Specific error message.
        code (str): Specific error code.
        section_code (str): Section code for the specific error.
        error_id (str): Unique identifier for the error instance.

    Methods:
        __init__(detail=None, code=None, section_code=None): Initializes the error with specific details.
        __str__(): Returns a formatted string representation of the error.
    """

    status_code = 500
    default_detail = "A server error occurred."
    default_code = "E5000"
    section_code = "SAGE"

    def __init__(self, detail=None, code=None, section_code=None):
        if detail is None:
            detail = self.default_detail
        if code is None:
            code = self.default_code
        if section_code is None:
            section_code = self.section_code
        self.detail = detail
        self.code = code
        self.section_code = section_code
        self.error_id = str(uuid.uuid4())

    def __str__(self):
        return f"Error {self.section_code}{self.code} - {self.detail} (Error ID: {self.error_id})"


class IMAPError(SageError):
    """Exception raised for general IMAP errors.

    Inherits from:
        SageError

    Attributes:
        status_code (int): HTTP status code associated with the error.
        default_detail (str): Default error message for IMAP errors.
        default_code (str): Default error code for IMAP errors.
        section_code (str): Section code for IMAP errors.
    """

    status_code = 500
    default_detail = "A Sage IMAP server error occurred."
    default_code = "E5001"
    section_code = "IMP"


class ConnectionError(IMAPError):
    """Exception raised for connection errors.

    Inherits from:
        IMAPError

    Attributes:
        status_code (int): HTTP status code associated with the error.
        default_detail (str): Default error message for connection errors.
        default_code (str): Default error code for connection errors.
        section_code (str): Section code for connection errors.
    """

    status_code = 502
    default_detail = "Failed to connect to Sage API. Please try again later."
    default_code = "E5002"
    section_code = "API"


class IMAPConfigurationError(IMAPError):
    """Exception raised for IMAP configuration errors.

    Inherits from:
        IMAPError

    Attributes:
        status_code (int): HTTP status code associated with the error.
        default_detail (str): Default error message for configuration errors.
        default_code (str): Default error code for configuration errors.
        section_code (str): Section code for configuration errors.
    """

    status_code = 400
    default_detail = "Invalid Sage IMAP configuration. Please check your settings."
    default_code = "E4001"
    section_code = "CFG"


class IMAPConnectionError(IMAPError):
    """Exception raised for IMAP connection errors.

    Inherits from:
        IMAPError

    Attributes:
        status_code (int): HTTP status code associated with the error.
        default_detail (str): Default error message for connection errors.
        default_code (str): Default error code for connection errors.
        section_code (str): Section code for connection errors.
    """

    status_code = 502
    default_detail = (
        "Failed to connect to Sage IMAP server. Please verify network settings."
    )
    default_code = "E5003"
    section_code = "IMC"


class IMAPAuthenticationError(IMAPError):
    """Exception raised for IMAP authentication errors.

    Inherits from:
        IMAPError

    Attributes:
        status_code (int): HTTP status code associated with the error.
        default_detail (str): Default error message for authentication errors.
        default_code (str): Default error code for authentication errors.
        section_code (str): Section code for authentication errors.
    """

    status_code = 401
    default_detail = (
        "Failed to authenticate with Sage IMAP server. Please check your credentials."
    )
    default_code = "E4002"
    section_code = "AUT"


class IMAPUnexpectedError(IMAPError):
    """Exception raised for unexpected IMAP errors.

    Inherits from:
        IMAPError

    Attributes:
        status_code (int): HTTP status code associated with the error.
        default_detail (str): Default error message for unexpected errors.
        default_code (str): Default error code for unexpected errors.
        section_code (str): Section code for unexpected errors.
    """

    status_code = 500
    default_detail = (
        "An unexpected error occurred with Sage IMAP. Please contact support."
    )
    default_code = "E5004"
    section_code = "UEX"
