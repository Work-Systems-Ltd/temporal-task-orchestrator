"""GenericTableView — reusable base class for table list pages.

Subclass, set class attributes, then call ``view.register(router)`` to
wire up both HTML and JSON API routes.  The base class handles query
param parsing, DB filtering/sorting/pagination, ORM→Pydantic conversion,
tab counts, data hashing, and template context building.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Generic, TypeVar

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from ui.auth.dependencies import require_auth
from ui.dependencies import get_db_service, get_templates
from core.db import DbService

from .query_parser import parse_filters
from .types import Column, FilterDef, QueryField, SortOption, TabConfig

M = TypeVar("M")  # ORM model
S = TypeVar("S", bound=BaseModel)  # Pydantic serializer


class GenericTableView(Generic[M, S]):
    """Base class for table list views.

    Subclass and set class attributes, then call ``register(router)``
    to create ``GET /prefix`` (HTML) and ``GET /api/prefix`` (JSON) routes.
    """

    # ── Required (set by subclass) ──
    model_class: type[M]
    serializer_class: type[S]
    template: str  # e.g. "tasks/list.html"
    url_prefix: str  # e.g. "/tasks"
    page_title: str = ""
    route_name: str = ""  # FastAPI route name for url_for()

    # ── Configuration ──
    tabs: TabConfig = TabConfig(order=["all"], labels={"all": "All"})
    columns: list[Column] = []
    filters: list[FilterDef] = []
    sort_options: list[SortOption] = []
    query_fields: list[QueryField] = []
    search_fields: list[str] = []

    default_sort: str = "created_at"
    default_order: str = "desc"
    default_per_page: int = 20

    # ── Hooks (override in subclass) ──

    def convert_record(self, record: M) -> S:
        """Convert an ORM record to a Pydantic display model. Must be overridden."""
        raise NotImplementedError

    async def get_access_filter(self, request: Request, db: DbService) -> list | None:
        """Return SQLAlchemy filter conditions for access control (OR'd), or None."""
        return None

    async def get_tab_counts(self, request: Request, db: DbService) -> dict[str, int]:
        """Compute counts per tab. Must be overridden."""
        raise NotImplementedError

    async def get_filter_options(self, key: str, request: Request, db: DbService) -> list[str]:
        """Return option values for a named filter dropdown."""
        return []

    def get_hash_exclude_fields(self) -> set[str]:
        """Fields to exclude from the data hash (e.g. relative time strings)."""
        return set()

    async def get_extra_context(self, request: Request, db: DbService) -> dict[str, Any]:
        """Additional template context beyond the standard fields."""
        return {}

    def get_simple_filter_conditions(
        self, request: Request, simple_filters: dict[str, str]
    ) -> list:
        """Convert simple dropdown filter values to SQLAlchemy conditions.

        Override for filters that don't map directly to a model column
        (e.g. ``assignment=mine`` needs to resolve the current user slug).
        Default implementation does direct column equality matches.
        """
        conditions = []
        for fdef in self.filters:
            value = simple_filters.get(fdef.key)
            if not value:
                continue
            col_name = fdef.field or fdef.key
            col = getattr(self.model_class, col_name, None)
            if col is not None:
                conditions.append(col == value)
        return conditions

    # ── Core query logic ──

    async def _build_query(
        self,
        request: Request,
        db: DbService,
        *,
        tab: str,
        page: int,
        per_page: int,
        sort_field: str,
        sort_order: str,
        search: str | None,
        simple_filters: dict[str, str],
        advanced_filters: list[str],
        filter_logic: str = "and",
    ) -> tuple[list[M], int]:
        """Build and execute the list query."""
        async with db._session() as session:
            stmt = select(self.model_class)
            count_stmt = select(func.count(self.model_class.id))

            # Tab / status filter
            if tab and tab != "all":
                status_col = getattr(self.model_class, self.tabs.status_field)
                if tab in self.tabs.status_groups:
                    statuses = self.tabs.status_groups[tab]
                    stmt = stmt.where(status_col.in_(statuses))
                    count_stmt = count_stmt.where(status_col.in_(statuses))
                else:
                    stmt = stmt.where(status_col == tab)
                    count_stmt = count_stmt.where(status_col == tab)

            # Simple filters (dropdown selections)
            for cond in self.get_simple_filter_conditions(request, simple_filters):
                stmt = stmt.where(cond)
                count_stmt = count_stmt.where(cond)

            # Advanced filters (query builder)
            if advanced_filters:
                conditions = parse_filters(
                    advanced_filters, self.model_class, self.query_fields, filter_logic
                )
                if conditions:
                    combined = (
                        or_(*conditions) if filter_logic == "or" else conditions
                    )
                    if isinstance(combined, list):
                        for c in combined:
                            stmt = stmt.where(c)
                            count_stmt = count_stmt.where(c)
                    else:
                        stmt = stmt.where(combined)
                        count_stmt = count_stmt.where(combined)

            # Search
            if search and self.search_fields:
                like = f"%{search}%"
                search_conds = [
                    getattr(self.model_class, f).ilike(like)
                    for f in self.search_fields
                    if hasattr(self.model_class, f)
                ]
                if search_conds:
                    filt = or_(*search_conds)
                    stmt = stmt.where(filt)
                    count_stmt = count_stmt.where(filt)

            # Access control
            access = await self.get_access_filter(request, db)
            if access is not None:
                stmt = stmt.where(or_(*access))
                count_stmt = count_stmt.where(or_(*access))

            # Count
            total = (await session.execute(count_stmt)).scalar() or 0

            # Sort
            sort_col = getattr(
                self.model_class, sort_field, getattr(self.model_class, self.default_sort)
            )
            stmt = stmt.order_by(
                sort_col.desc() if sort_order == "desc" else sort_col.asc()
            )

            # Paginate
            offset = (page - 1) * per_page
            stmt = stmt.offset(offset).limit(per_page)

            rows = list((await session.execute(stmt)).scalars().all())
            return rows, total

    def _compute_hash(self, items: list[S], total: int) -> str:
        """Compute an MD5 hash of the result set for WebSocket change detection."""
        exclude = self.get_hash_exclude_fields()
        stable = [
            {k: v for k, v in item.model_dump().items() if k not in exclude}
            for item in items
        ]
        return hashlib.md5(
            json.dumps({"items": stable, "total": total}, sort_keys=True, default=str).encode()
        ).hexdigest()

    # ── Route handler factories ──

    def _parse_common_params(self, request: Request, tab, page, per_page, sort_by, q):
        """Parse common query parameters shared by HTML and API handlers."""
        effective_tab = tab or self.tabs.default_tab or self.tabs.order[0]
        if effective_tab not in self.tabs.order:
            effective_tab = self.tabs.default_tab or self.tabs.order[0]

        search = q.strip() if q else None

        sort_field = self.default_sort
        sort_order = self.default_order
        if sort_by and ":" in sort_by:
            parts = sort_by.split(":", 1)
            sort_field, sort_order = parts[0], parts[1]

        simple_filters = {}
        for f in self.filters:
            val = request.query_params.get(f.key, "")
            if val:
                simple_filters[f.key] = val

        advanced_filters = request.query_params.getlist("filter")
        filter_logic = request.query_params.get("filter_logic", "and")

        return {
            "tab": effective_tab,
            "search": search,
            "sort_field": sort_field,
            "sort_order": sort_order,
            "simple_filters": simple_filters,
            "advanced_filters": advanced_filters,
            "filter_logic": filter_logic,
        }

    def _make_html_handler(self):
        """Create the GET /prefix → HTML handler."""
        view = self

        async def handler(
            request: Request,
            tab: str = Query(None),
            page: int = Query(1, ge=1),
            per_page: int = Query(None, ge=10, le=100),
            sort_by: str | None = Query(None),
            q: str | None = Query(None),
            db: DbService = Depends(get_db_service),
            templates: Jinja2Templates = Depends(get_templates),
        ) -> HTMLResponse:
            effective_per_page = per_page or view.default_per_page
            params = view._parse_common_params(request, tab, page, effective_per_page, sort_by, q)

            records, total = await view._build_query(
                request, db,
                tab=params["tab"],
                page=page,
                per_page=effective_per_page,
                sort_field=params["sort_field"],
                sort_order=params["sort_order"],
                search=params["search"],
                simple_filters=params["simple_filters"],
                advanced_filters=params["advanced_filters"],
                filter_logic=params["filter_logic"],
            )

            items = [view.convert_record(r) for r in records]
            tab_counts = await view.get_tab_counts(request, db)

            # Collect filter options
            filter_options: dict[str, list[str]] = {}
            for f in view.filters:
                filter_options[f.key] = await view.get_filter_options(f.key, request, db)

            has_next = (page * effective_per_page) < total
            total_pages = (total + effective_per_page - 1) // effective_per_page if total > 0 else 1
            data_hash = view._compute_hash(items, total)

            extra = await view.get_extra_context(request, db)

            context = {
                "request": request,
                "items": items,
                "page": page,
                "total": total,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_prev": page > 1,
                "per_page": effective_per_page,
                # Tabs
                "tab": params["tab"],
                "tab_config": view.tabs,
                "tab_counts": tab_counts,
                # Columns
                "columns": view.columns,
                # Filters
                "filters": view.filters,
                "filter_values": {f.key: request.query_params.get(f.key, "") for f in view.filters},
                "filter_options": filter_options,
                "search": params["search"] or "",
                # Sort
                "sort_by": sort_by or f"{view.default_sort}:{view.default_order}",
                "sort_options": view.sort_options,
                # Query builder
                "query_fields": view.query_fields,
                "advanced_filters": params["advanced_filters"],
                "filter_logic": params["filter_logic"],
                # Meta
                "data_hash": data_hash,
                "url_prefix": view.url_prefix,
                "page_title": view.page_title,
                "view": view,
                **extra,
            }

            return templates.TemplateResponse(view.template, context)

        # Set function name for FastAPI route naming
        handler.__name__ = view.route_name or view.url_prefix.strip("/") + "_page"
        return handler

    def _make_api_handler(self):
        """Create the GET /api/prefix → JSON handler."""
        view = self

        async def handler(
            request: Request,
            tab: str = Query(None),
            page: int = Query(1, ge=1),
            per_page: int = Query(None, ge=10, le=100),
            sort_by: str | None = Query(None),
            q: str | None = Query(None),
            db: DbService = Depends(get_db_service),
        ) -> JSONResponse:
            effective_per_page = per_page or view.default_per_page
            params = view._parse_common_params(request, tab, page, effective_per_page, sort_by, q)

            records, total = await view._build_query(
                request, db,
                tab=params["tab"],
                page=page,
                per_page=effective_per_page,
                sort_field=params["sort_field"],
                sort_order=params["sort_order"],
                search=params["search"],
                simple_filters=params["simple_filters"],
                advanced_filters=params["advanced_filters"],
                filter_logic=params["filter_logic"],
            )

            items = [view.convert_record(r) for r in records]
            tab_counts = await view.get_tab_counts(request, db)
            data_hash = view._compute_hash(items, total)

            return JSONResponse({
                "items": [item.model_dump() for item in items],
                "total": total,
                "page": page,
                "per_page": effective_per_page,
                "has_next": (page * effective_per_page) < total,
                "tab_counts": tab_counts,
                "data_hash": data_hash,
            })

        handler.__name__ = "api_" + (view.route_name or view.url_prefix.strip("/"))
        return handler

    def register(self, router: APIRouter) -> None:
        """Register HTML and JSON API routes on the given router."""
        name = self.route_name or self.url_prefix.strip("/") + "_page"
        router.add_api_route(
            self.url_prefix,
            self._make_html_handler(),
            methods=["GET"],
            response_class=HTMLResponse,
            name=name,
        )
        router.add_api_route(
            f"/api{self.url_prefix}",
            self._make_api_handler(),
            methods=["GET"],
            name=f"api_{name}",
        )
