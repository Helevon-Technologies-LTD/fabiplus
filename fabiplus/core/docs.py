"""
FABI+ Framework Documentation Customization
Custom OpenAPI docs with FABI+ branding
"""

from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def get_custom_openapi(
    app: FastAPI,
    title: str = "FABI+ API",
    version: str = "1.0.0",
    description: str = "API built with FABI+ Framework",
    logo_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate custom OpenAPI schema with FABI+ branding
    """

    if app.openapi_schema:
        return app.openapi_schema

    # Default FABI+ logo placeholder
    if not logo_url:
        logo_url = "/static/fabiplus-logo.png"  # Placeholder for custom logo

    openapi_schema = get_openapi(
        title=title,
        version=version,
        description=description,
        routes=app.routes,
    )

    # Add custom FABI+ branding
    openapi_schema["info"]["x-logo"] = {"url": logo_url, "altText": "FABI+ Framework"}

    # Add custom description with FABI+ branding
    custom_description = f"""
{description}

---

**Powered by FABI+ Framework**

FABI+ combines the async speed of FastAPI with the admin robustness of Django, 
providing automatic settings management, built-in admin dashboard, and production-ready features.

**Features:**
- 🚀 **High Performance**: Built on FastAPI with async support
- 🛡️ **Admin Interface**: Built-in admin API with web interface support  
- 🔧 **Auto-Generated APIs**: Automatic CRUD endpoints for all models
- 🔐 **Authentication**: OAuth2/JWT authentication with custom backend support
- 🛡️ **Security**: CSRF protection, XSS protection, CORS, and security headers
- 📊 **Caching**: Multi-backend caching (memory, Redis) for performance
- 🧪 **Testing**: Comprehensive test framework
- 🐳 **Production Ready**: Docker support, monitoring, and deployment tools

**Links:**
- [FABI+ Documentation](https://docs.fabiplus.dev)
- [GitHub Repository](https://github.com/fabiplus/fabiplus)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Django Documentation](https://docs.djangoproject.com)
"""

    openapi_schema["info"]["description"] = custom_description

    # Add custom contact and license info
    openapi_schema["info"]["contact"] = {
        "name": "FABI+ Framework",
        "url": "https://fabiplus.dev",
        "email": "support@fabiplus.dev",
    }

    openapi_schema["info"]["license"] = {
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    }

    # Add custom tags for better organization
    openapi_schema["tags"] = [
        {
            "name": "Authentication",
            "description": "User authentication and authorization endpoints",
        },
        {
            "name": "Admin",
            "description": "Admin interface endpoints for content management",
        },
        {"name": "Cache", "description": "Cache management endpoints"},
        {"name": "Health", "description": "Health check and monitoring endpoints"},
    ]

    # Add custom servers
    openapi_schema["servers"] = [
        {"url": "/", "description": "Current server"},
        {
            "url": "https://api.example.com",
            "description": "Production server (replace with your domain)",
        },
    ]

    # Add custom extensions
    openapi_schema["x-tagGroups"] = [
        {"name": "Core API", "tags": ["Authentication", "Health"]},
        {"name": "Admin", "tags": ["Admin", "Cache"]},
        {"name": "Models", "tags": []},  # Will be populated with model tags
    ]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


def setup_docs_customization(app: FastAPI, settings):
    """
    Setup custom documentation for FABI+ app
    """

    def custom_openapi():
        try:
            return get_custom_openapi(
                app=app,
                title=settings.APP_NAME,
                version=settings.APP_VERSION,
                description=f"{settings.APP_NAME} - Built with FABI+ Framework",
            )
        except Exception as e:
            # Fallback to default OpenAPI if custom fails
            print(f"Warning: Custom OpenAPI failed, using default: {e}")
            return get_openapi(
                title=settings.APP_NAME,
                version=settings.APP_VERSION,
                description=f"{settings.APP_NAME} - Built with FABI+ Framework",
                routes=app.routes,
            )

    app.openapi = custom_openapi


# Custom CSS for documentation
CUSTOM_DOCS_CSS = """
<style>
/* FABI+ Custom Documentation Styles */

/* Header customization */
.swagger-ui .topbar {
    background-color: #1e40af;
    border-bottom: 3px solid #3b82f6;
}

.swagger-ui .topbar .download-url-wrapper {
    display: none;
}

/* Logo area */
.swagger-ui .topbar-wrapper img {
    max-height: 40px;
}

/* Custom FABI+ branding */
.swagger-ui .info .title {
    color: #1e40af;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.swagger-ui .info .description {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Operation styling */
.swagger-ui .opblock.opblock-get {
    border-color: #10b981;
    background: rgba(16, 185, 129, 0.1);
}

.swagger-ui .opblock.opblock-post {
    border-color: #3b82f6;
    background: rgba(59, 130, 246, 0.1);
}

.swagger-ui .opblock.opblock-put {
    border-color: #f59e0b;
    background: rgba(245, 158, 11, 0.1);
}

.swagger-ui .opblock.opblock-delete {
    border-color: #ef4444;
    background: rgba(239, 68, 68, 0.1);
}

/* Custom footer */
.swagger-ui .info::after {
    content: "Powered by FABI+ Framework - FastAPI + Django Admin";
    display: block;
    margin-top: 20px;
    padding: 10px;
    background: linear-gradient(135deg, #1e40af, #3b82f6);
    color: white;
    border-radius: 8px;
    text-align: center;
    font-weight: 500;
}

/* Responsive design */
@media (max-width: 768px) {
    .swagger-ui .info .title {
        font-size: 24px;
    }
}
</style>
"""

# Custom JavaScript for enhanced functionality
CUSTOM_DOCS_JS = """
<script>
// FABI+ Documentation Enhancements

document.addEventListener('DOMContentLoaded', function() {
    // Add FABI+ branding
    const title = document.querySelector('.swagger-ui .info .title');
    if (title) {
        title.innerHTML += ' <span style="color: #10b981; font-size: 0.8em;">powered by FABI+</span>';
    }
    
    // Add performance metrics
    const startTime = performance.now();
    window.addEventListener('load', function() {
        const loadTime = performance.now() - startTime;
        console.log(`FABI+ API Documentation loaded in ${loadTime.toFixed(2)}ms`);
    });
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + K to focus search
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.querySelector('.swagger-ui .download-url-wrapper input');
            if (searchInput) {
                searchInput.focus();
            }
        }
    });
});
</script>
"""


def get_custom_docs_html(title: str = "FABI+ API Documentation") -> str:
    """
    Generate custom HTML for documentation with FABI+ branding
    """

    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <link rel="shortcut icon" href="/static/favicon.ico">
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@3.52.5/swagger-ui.css" />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    {CUSTOM_DOCS_CSS}
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@3.52.5/swagger-ui-bundle.js"></script>
    <script>
        const ui = SwaggerUIBundle({{
            url: '/openapi.json',
            dom_id: '#swagger-ui',
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIBundle.presets.standalone
            ],
            layout: "StandaloneLayout",
            deepLinking: true,
            showExtensions: true,
            showCommonExtensions: true,
            docExpansion: "list",
            filter: true,
            tryItOutEnabled: true,
            requestInterceptor: function(request) {{
                // Add custom headers or modify requests
                request.headers['X-Powered-By'] = 'FABI+';
                return request;
            }},
            responseInterceptor: function(response) {{
                // Log API response times
                console.log('API Response Time:', response.duration + 'ms');
                return response;
            }}
        }});
    </script>
    {CUSTOM_DOCS_JS}
</body>
</html>
"""


# Import StaticFiles for static file serving
try:
    from fastapi.staticfiles import StaticFiles
except ImportError:
    # Fallback if not available
    StaticFiles = None
