"""Pagination utilities."""

from typing import Any, Dict, List, Optional, Sequence, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PageParams(BaseModel):
    """Pagination parameters."""

    page: int = 1
    size: int = 20


def paginate(
    items: Sequence,
    total: int,
    page: int,
    size: int,
) -> Dict[str, Any]:
    """Create paginated response dict."""
    return {
        "items": list(items),
        "total": total,
        "page": page,
        "size": size,
        "total_pages": (total + size - 1) // size if size > 0 else 0,
    }


def get_skip_limit(page: int, size: int) -> tuple[int, int]:
    """Calculate skip and limit from page/size."""
    return (page - 1) * size, size