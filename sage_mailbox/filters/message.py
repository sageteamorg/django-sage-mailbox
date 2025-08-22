import django_filters
from django.db.models import Q
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.contrib.postgres.search import SearchVector, SearchQuery
from django.contrib.postgres.search import TrigramSimilarity

from sage_mailbox.models import EmailMessage


class MailboxMessageFilter(django_filters.FilterSet):
    """FilterSet for filtering EmailMessage queryset by various parameters."""

    search = django_filters.CharFilter(
        method="heavy_search", label=_("Search by Subject, Plain Body, or HTML Body")
    )
    from_address = django_filters.CharFilter(
        field_name="from_address", lookup_expr="iexact", label=_("From Address")
    )
    to_address = django_filters.CharFilter(
        field_name="to_address", lookup_expr="icontains", label=_("To Address")
    )
    cc_address = django_filters.CharFilter(
        field_name="cc_address", lookup_expr="icontains", label=_("CC Address")
    )
    bcc_address = django_filters.CharFilter(
        field_name="bcc_address", lookup_expr="icontains", label=_("BCC Address")
    )
    is_read = django_filters.BooleanFilter(
        field_name="is_read", label=_("Is Read")
    )
    is_flagged = django_filters.BooleanFilter(
        field_name="is_flagged", label=_("Is Flagged")
    )
    size_min = django_filters.NumberFilter(
        field_name="size", lookup_expr="gte", label=_("Minimum Size (bytes)")
    )
    size_max = django_filters.NumberFilter(
        field_name="size", lookup_expr="lte", label=_("Maximum Size (bytes)")
    )
    date_min = django_filters.DateTimeFilter(
        field_name="date", lookup_expr="gte", label=_("Earliest Date")
    )
    date_max = django_filters.DateTimeFilter(
        field_name="date", lookup_expr="lte", label=_("Latest Date")
    )
    mailbox = django_filters.CharFilter(
        field_name="mailbox__name", lookup_expr="iexact", label=_("Mailbox Name")
    )
    sort_by = django_filters.ChoiceFilter(
        method="sort_queryset",
        label=_("Sort By"),
        choices=[
            ("date", "Date (Newest First)"),
            ("-date", "Date (Oldest First)"),
            ("size", "Size (Smallest First)"),
            ("-size", "Size (Largest First)"),
        ],
    )

    class Meta:
        model = EmailMessage
        fields = [
            "from_address",
            "to_address",
            "cc_address",
            "bcc_address",
            "is_read",
            "is_flagged",
            "mailbox",
            "size",
            "date",
        ]

    def sort_queryset(self, queryset, name, value):
        """Sort the queryset based on the selected sort option."""
        if value:
            return queryset.order_by(value)
        return queryset

    def full_text_search(self, queryset, search_query):
        """Performs a full-text search on 'subject', 'plain_body', and 'html_body' fields of the emails."""
        database_engine = settings.DATABASES["default"]["ENGINE"]
        if search_query:
            if "postgresql" in database_engine:
                vector = SearchVector("subject", "plain_body", "html_body")
                query = SearchQuery(search_query)
                return queryset.annotate(search=vector).filter(search=query)

            elif "mysql" in database_engine or "mariadb" in database_engine:
                return queryset.filter(
                    Q(subject__icontains=search_query)
                    | Q(plain_body__icontains=search_query)
                    | Q(html_body__icontains=search_query)
                )

            elif "sqlite" in database_engine:
                return queryset.filter(
                    Q(subject__icontains=search_query)
                    | Q(plain_body__icontains=search_query)
                    | Q(html_body__icontains=search_query)
                )
        return queryset

    def substring_search(self, queryset, search_query):
        """Performs a case-insensitive substring search in 'subject', 'plain_body', and 'html_body' fields."""
        if search_query:
            return queryset.filter(
                Q(subject__icontains=search_query)
                | Q(plain_body__icontains=search_query)
                | Q(html_body__icontains=search_query)
            )
        return queryset

    def trigram_similarity_search(self, queryset, search_query):
        """Performs a search using trigram similarity on 'subject', 'plain_body', and 'html_body' fields."""
        database_engine = settings.DATABASES["default"]["ENGINE"]

        if "postgresql" in database_engine:
            return (
                queryset.annotate(
                    similarity=TrigramSimilarity("subject", search_query)
                    + TrigramSimilarity("plain_body", search_query)
                    + TrigramSimilarity("html_body", search_query)
                )
                .filter(similarity__gt=0.1)
                .order_by("-similarity")
            )

        elif "mysql" in database_engine or "mariadb" in database_engine:
            return queryset.filter(
                Q(subject__icontains=search_query)
                | Q(plain_body__icontains=search_query)
                | Q(html_body__icontains=search_query)
            )

        elif "sqlite" in database_engine:
            return queryset.filter(
                Q(subject__icontains=search_query)
                | Q(plain_body__icontains=search_query)
                | Q(html_body__icontains=search_query)
            )

        return queryset.none()

    def heavy_search(self, queryset, name, search_query):
        """Combines full-text search, substring search, and trigram similarity search."""
        if not search_query:
            return queryset

        # Step 1: Full-text search
        full_text_qs = self.full_text_search(queryset, search_query)
        if full_text_qs.exists():
            return full_text_qs

        # Step 2: Substring search
        substring_qs = self.substring_search(queryset, search_query)
        if substring_qs.exists():
            return substring_qs

        # Step 3: Trigram similarity search (if supported by the database)
        trigram_qs = self.trigram_similarity_search(queryset, search_query)
        if trigram_qs.exists():
            return trigram_qs

        return queryset.none()
