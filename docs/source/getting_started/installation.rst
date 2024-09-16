Installation
============

Installing `django-sage-mailbox` is like below:

Using `pip` with `virtualenv`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. **Create a Virtual Environment**:

   .. code-block:: bash

      python -m venv .venv

2. **Activate the Virtual Environment**:
   
   - On Windows:

     .. code-block:: bash

        .venv\Scripts\activate

   - On macOS/Linux:

     .. code-block:: bash

        source .venv/bin/activate

3. **Install `django-sage-mailbox`**:

   .. code-block:: bash

      pip install django-sage-mailbox

Using `poetry`
~~~~~~~~~~~~~~

1. **Initialize Poetry** (if not already initialized):

   .. code-block:: bash

      poetry init

2. **Install `django-sage-mailbox`**:

   .. code-block:: bash

      poetry add django-sage-mailbox

Django Settings Configuration
-----------------------------

Installed Apps
~~~~~~~~~~~~~~

To use `django-sage-mailbox`, add it to your `INSTALLED_APPS` in the Django settings:

.. code-block:: python

    INSTALLED_APPS = [
        # other packages
        "django.contrib.sites",
        "sage_mailbox",
        "django_jsonform",
    ]

Additional Configuration for IMAP and Email
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configure your IMAP and email settings in `settings.py`:

.. code-block:: python

   SITE_ID = 1

   # IMAP Server Configuration
   IMAP_SERVER_DOMAIN = "your.imap.server"
   IMAP_SERVER_PORT = 993
   IMAP_SERVER_USER = "your-email@example.com"
   IMAP_SERVER_PASSWORD = "your-password"

   # Email Backend Configuration
   EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
   EMAIL_HOST = "your.smtp.server"
   EMAIL_PORT = 465
   # EMAIL_USE_TLS = True
   EMAIL_USE_SSL = True
   EMAIL_HOST_USER = "your-email@example.com"
   EMAIL_HOST_PASSWORD = "your-password"

   # Default Email Settings
   DEFAULT_FROM_EMAIL = "your-email@example.com"
   SERVER_EMAIL = "your-email@example.com"

   # Custom Email Headers
   DEFAULT_EMAIL_HEADERS = {
       "X-Mailer": "sage_imap",
       "List-Unsubscribe": "<mailto:unsubscribe@example.com>",
       "Return-Path": "<bounce@example.com>",
       "Reply-To": "replyto@example.com",
       "X-Priority": "3",
       "X-Report-Abuse-To": "abuse@example.com",
       "X-Spamd-Result": "default",
       "X-Auto-Response-Suppress": "All",
   }
