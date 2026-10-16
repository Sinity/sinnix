"""Install the shared admission policy on vendor FastAPI applications."""

from sinnix_ai_browser_boundary import BrowserBoundary


def admit_fastapi(app, *, allowed_ports, allow_credentials=False):
    """Surround existing vendor middleware, including any request-body readers."""
    from fastapi.middleware.cors import CORSMiddleware

    policy = BrowserBoundary(None, allowed_ports=allowed_ports)
    origins = [
        f"http://{('[' + host + ']') if ':' in host else host}:{port}"
        for host in sorted(policy.hosts)
        for port in sorted(policy.ports)
    ]
    app.user_middleware = [
        middleware
        for middleware in app.user_middleware
        if middleware.cls is not CORSMiddleware
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(BrowserBoundary, allowed_ports=policy.ports)
    return app
