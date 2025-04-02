from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
from urllib.parse import quote, urlencode
from urllib.parse import urlparse, parse_qs


class HTMXRedirectMiddleware(BaseHTTPMiddleware):
    """
    Middleware to redirect non-HTMX requests to the root path,
    except for static files and API endpoints.
    """
    async def dispatch(self, request: Request, call_next):
        # Static file paths that should be allowed
        static_paths = ["/build/", "/sse", "/blobs/upload-multi", "/tags/autocomplete"]

        # Check if the request is for a static file
        is_static = any(request.url.path.startswith(path) for path in static_paths)

        # Check if the request has the HTMX header
        is_htmx = request.headers.get("HX-Request") == "true"

        # If not an HTMX request, not a static file, and not already targeting the root path
        if not is_htmx and not is_static and request.url.path != "/":
            # Encode the original path, query, and hash to pass as a parameter
            parsed_url = urlparse(str(request.url))
            original_path = quote(parsed_url.path)
            query_params = parse_qs(parsed_url.query)
            encoded_query = urlencode(query_params, doseq=True)
            fragment = quote(parsed_url.fragment) if parsed_url.fragment else ""

            redirect_url = "/?"
            if original_path:
                redirect_url += f"target_path={original_path}"
            if encoded_query:
                redirect_url += f"?{encoded_query}" if original_path else f"{encoded_query}"
            if fragment:
                redirect_url += f"#{fragment}"

            return RedirectResponse(url=redirect_url)

        return await call_next(request)
