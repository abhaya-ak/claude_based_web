from rest_framework.pagination import LimitOffsetPagination


class StandardPagination(LimitOffsetPagination):
    """Standard limit/offset pagination with default 20 and max 100."""

    default_limit = 20
    max_limit = 100
