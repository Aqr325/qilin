"""Common Pydantic schemas: pagination, unified response."""

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ── Unified Response ──

class ApiResponse(BaseModel, Generic[T]):
    """Unified API success response."""

    code: int = 200
    message: str = Field(default="success")
    data: Optional[T] = None
    request_id: Optional[str] = None


class ErrorResponse(BaseModel):
    """Unified API error response."""

    code: int
    message: str
    detail: Optional[str] = None
    request_id: Optional[str] = None


# ── Pagination ──

class PageParams(BaseModel):
    """Pagination query parameters."""

    page: int = Field(default=1, ge=1, description="页码")
    size: int = Field(default=20, ge=1, le=100, description="每页条数")


class Page(BaseModel, Generic[T]):
    """Paginated response data."""

    items: List[T] = Field(default_factory=list)
    total: int = Field(default=0)
    page: int = Field(default=1)
    size: int = Field(default=20)
    total_pages: int = Field(default=0)

    @classmethod
    def create(cls, items: List[T], total: int, page: int, size: int) -> "Page[T]":
        return cls(
            items=items,
            total=total,
            page=page,
            size=size,
            total_pages=(total + size - 1) // size if size > 0 else 0,
        )


class FilterSummary(BaseModel):
    """Filter summary for list endpoints."""

    status_filter: Optional[str] = None
    severity_filter: Optional[str] = None
    time_range: Optional[str] = None


# ── Common Types ──

class IdNamePair(BaseModel):
    """Simple ID + Name pair."""

    id: str
    name: str
    display_name: Optional[str] = None


class TimeRangeQuery(BaseModel):
    """Time range query parameters."""

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    time_range: Optional[str] = Field(default=None, description="快捷时间范围: 1h/24h/7d/30d")


class SortParams(BaseModel):
    """Sort parameters."""

    sort_by: Optional[str] = None
    sort_order: Optional[str] = Field(default="desc", pattern="^(asc|desc)$")