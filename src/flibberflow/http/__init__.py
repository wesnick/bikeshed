from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

class HTMXRedirectMiddleware(BaseHTTPMiddleware):
    """
    Middleware to redirect non-HTMX requests to the root path,
    except for static files and API endpoints.
    """
    async def dispatch(self, request: Request, call_next):
        # Static file paths that should be allowed
        static_paths = ["/build/", "/sse"]
        
        # Check if the request is for a static file
        is_static = any(request.url.path.startswith(path) for path in static_paths)
        
        # Check if the request has the HTMX header
        is_htmx = request.headers.get("HX-Request") == "true"

        # If not an HTMX request, not a static file, and not already targeting the root path
        if not is_htmx and not is_static and request.url.path != "/":
            return RedirectResponse(url="/")

        # Otherwise proceed with normal request handling
        response = await call_next(request)
        return response
