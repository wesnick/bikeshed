from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

class HTMXRedirectMiddleware(BaseHTTPMiddleware):
    """
    Middleware to redirect non-HTMX requests to the root path.
    """
    async def dispatch(self, request: Request, call_next):

        # Check if the request has the HTMX header
        is_htmx = request.headers.get("HX-Request") == "true"

        # If not an HTMX request and not already targeting the root path
        if not is_htmx and request.url.path != "/":
            return RedirectResponse(url="/")

        # Otherwise proceed with normal request handling
        response = await call_next(request)
        return response
