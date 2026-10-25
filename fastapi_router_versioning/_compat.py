from collections.abc import Callable, Iterator
from typing import Any

import fastapi.routing

from fastapi.routing import APIRoute, APIWebSocketRoute

# iter_route_contexts was introduced in FastAPI 0.137.2. On older versions the
# attribute does not exist and getattr returns None, activating the fallback path.
_route_contexts_fn: Callable[..., Any] | None = getattr(fastapi.routing, "iter_route_contexts", None)


def iter_routes_flat(routes: list[Any]) -> Iterator[Any]:
    """Flattens the route tree, or yields it unchanged where iter_route_contexts is missing."""
    if _route_contexts_fn is None:
        yield from routes
        return

    for route_ctx in _route_contexts_fn(routes):
        original = route_ctx.original_route
        if isinstance(original, APIRoute):
            # RouteContext merges path/tags/deps via __getattr__; use the context directly.
            yield route_ctx
        elif isinstance(original, APIWebSocketRoute):
            if route_ctx.path:
                yield route_ctx
            else:
                # FastAPI 0.137.2-0.143.0 resolve a nested WebSocket context to an empty path,
                # name and dependencies (fixed in 0.143.1). The fully resolved route is only on
                # the private _route_context; those releases are frozen, so it cannot move.
                yield route_ctx._route_context.starlette_route
        else:
            yield original  # pragma: no cover


def unwrap_route(route: Any) -> Any:
    # RouteContext (FastAPI >= 0.137.2) wraps the original route.
    # Attributes like response_model, status_code, operation_id live on the original.
    return getattr(route, "original_route", route)
