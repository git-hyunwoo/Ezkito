# ezkito (on service : https://ezkito.com/)
> **Extreme Lightweight Image Processing Web Service**
> *Crafted for high efficiency in resource-constrained environments (512MB RAM).*

<p align="left">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Django-5.x-092E20?logo=django&logoColor=white" alt="Django">
  <img src="https://img.shields.io/badge/SQLite-Latest-003B57?logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/Render-Free%20Tier-46E3B7?logo=render&logoColor=white" alt="Render">
</p>

---

## 🚀 Overview
**ezkito** is a specialized web tool for quick and easy image editing. The core challenge was to provide seamless image manipulation features (Conversion, Background Removal, Cropping) within an **extremely limited server environment**.

## 🛠 Technical Specifications
The system architecture is strictly optimized to survive and perform on a **"Hobby Plan"** instance.

### 💻 Infrastructure (The "Survival" Spec)
| Component | Specification | Details |
| :--- | :--- | :--- |
| **Platform** | Cloud PaaS (Render) | Free Tier Instance |
| **Memory** | **512 MB RAM** | Optimized for low-memory footprint |
| **Processor** | **0.1 Shared vCPU** | Minimalistic computational overhead |
| **Storage** | Ephemeral | Stateless architecture for fast scaling |

### Software Stack
* **Backend :** `Django 5.x` — Robust and scalable framework.
* **WSGI Server :** `Gunicorn` — Configured with `--workers 1` to prevent Out-Of-Memory (OOM) crashes.
* **Database :** `SQLite` — Zero-process overhead; runs directly on the file system to save RAM.
* **Static Files :** `WhiteNoise` — Serves assets directly via Django, eliminating the need for a separate Nginx process.

## Image Processing Engine
To handle high-resolution images on a 512MB RAM server, **ezkito** employs several optimization strategies:

* **Pillow (PIL) :** Efficient format conversion, resizing, and filtering using lazy-loading techniques.
* **Rembg / External API :** Background removal is processed via optimized local logic or offloaded to external APIs if RAM limits are reached.
* **Client-side Offloading :** Basic geometric transforms and UI previews are handled by the user's browser (**JavaScript/Canvas API**) to minimize server-side CPU load.

## ⚡ Optimization Strategy
1. **Strict Concurrency Control :** Single worker/limited thread configuration to maintain a stable memory ceiling.
2. **Memory-efficient Caching :** Optional local memory cache with strict TTL and size constraints.
3. **Atomic File Handling :** Temporary files are immediately purged after processing to prevent disk overflow.

---

## 📂 Project Structure
```text
ezkito/
├── core/               # Project configuration
├── image_engine/       # Core logic for conversion & background removal
├── static/             # Client-side processing scripts
└── templates/          # Responsive UI layouts
