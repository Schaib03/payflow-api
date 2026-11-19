from rest_framework.pagination import CursorPagination


class CreatedAtCursorPagination(CursorPagination):
    """Cursor pagination is stable while new rows are inserted, unlike offsets."""

    ordering = "-created_at"
    page_size_query_param = "limit"
    max_page_size = 100
