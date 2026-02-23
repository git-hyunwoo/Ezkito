# Ezkito


on service : https://ezkito.com/

🛠 Technical Specifications
1. Core Environment (Infrastructure)
Platform: Cloud PaaS (e.g., Render.com, Fly.io) Free Tier Instance

RAM: 512 MB (Optimized for low-memory footprints)

CPU: 0.1 Shared vCPU

Storage: Ephemeral Storage (Stateless architecture)

Network: Standard HTTP/HTTPS Inbound/Outbound

2. Software Stack
Language: Python 3.10+ (Utilizing latest memory management improvements)

Framework: Django 5.x

WSGI Server: Gunicorn (Configured with --workers 1 to prevent OOM errors)

Database: SQLite (Zero-process overhead; runs directly on the file system to save RAM)

3. Image Processing Engine
Pillow (PIL): Used for lightweight format conversion, resizing, and filtering.

Rembg / External API: Specialized for background removal (Offloaded to API if local RAM exceeds limits).

JavaScript (Client-side): Offloads UI previews and basic geometric transforms to the user's browser to reduce server load.

4. Deployment Configuration (Optimization)
Static Files: WhiteNoise (Serves static assets directly via Django without needing a separate Nginx process).

Concurrency: Single worker with limited threads to maintain a stable memory ceiling.

Caching: Optional local memory cache with strict TTL and size limits.
