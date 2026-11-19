from rest_framework.pagination import CursorPagination


class CreatedAtCursorPagination(CursorPagination):
    ordering = "-created_at"
    page_size_query_param = "limit"
    max_page_size = 100
