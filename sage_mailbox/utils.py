import re


def sanitize_filename(filename):
    """Sanitize the filename to ensure it's safe to use in the file system."""
    # Decode if the filename is encoded
    if filename.startswith("=?"):
        from email.header import decode_header

        decoded_header = decode_header(filename)
        filename = "".join(
            part.decode(encoding or "utf-8") if isinstance(part, bytes) else part
            for part, encoding in decoded_header
        )

    # Split the filename into name and extension
    name, ext = re.match(r"(.+?)(\.[^.]*$|$)", filename).groups()

    # Sanitize the name part
    name = re.sub(r"[^A-Za-z0-9_\-]", "_", name)

    # Reconstruct the filename with the sanitized name and original extension
    sanitized_filename = name + ext

    return sanitized_filename


def create_proxy_model(base_model, proxy_name, new_methods=None):
    class Meta:
        proxy = True
        app_label = base_model._meta.app_label

    attrs = {"__module__": base_model.__module__, "Meta": Meta}

    if new_methods:
        attrs.update(new_methods)

    return type(proxy_name, (base_model,), attrs)


def map_to_standard_name(imap_name):
    from sage_mailbox.models.mailbox import IMAP_TO_STANDARD_MAP, StandardMailboxNames

    # Normalize the name using casefold for a more aggressive comparison
    normalized_name = imap_name.casefold()

    # Remove surrounding quotes if present
    normalized_name = normalized_name.strip("'\"")

    # Define patterns to intelligently map names containing specific keywords
    patterns = {
        "inbox": StandardMailboxNames.INBOX,
        "sent": StandardMailboxNames.SENT,
        "draft": StandardMailboxNames.DRAFTS,
        "junk": StandardMailboxNames.SPAM,
        "spam": StandardMailboxNames.SPAM,
        "trash": StandardMailboxNames.TRASH,
        "deleted": StandardMailboxNames.TRASH,
    }

    # Check for exact matches in the mapping dictionary
    if normalized_name in IMAP_TO_STANDARD_MAP:
        return IMAP_TO_STANDARD_MAP[normalized_name]

    # Check for keyword patterns in the normalized name
    for pattern, standard_name in patterns.items():
        if re.search(pattern, normalized_name):
            return standard_name

    # Default to the original name if no match is found
    return StandardMailboxNames.CUSTOM
