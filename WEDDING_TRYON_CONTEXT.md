# WEDDING VIRTUAL TRY-ON — Full Project Context for Claude Code

## ROLE
You are a senior AI solutions architect and full-stack engineer building an AI-powered Wedding Virtual Try-On prototype.

---

## GOAL
- Customer uploads their photo and a wedding dress image.
- System generates a realistic virtual try-on image (customer wearing the dress) using CatVTON.
- The try-on result is then passed to an image generation model which creates a realistic Indian wedding scene with elegant mandap stage decoration, marigold and rose floral arrangements, draped fabric canopy in gold and red, diyas and string lights, cinematic soft lighting, luxury wedding ambiance.
- The final scene image is saved to local filesystem and displayed in the UI.

---

## TECH STACK

### Frontend
- React 18 + TypeScript
- Vite as build tool
- Axios for API calls
- Tailwind CSS for styling
- Components: drag-and-drop image upload, 4-step progress stepper, side-by-side image previews (try-on result + final scene), download button

### Backend
- Python 3.11+ with FastAPI
- Pydantic v2 + pydantic-settings for config and validation
- structlog for structured logging (coloured in dev, JSON in prod)
- Pillow for image processing
- aiofiles for async file I/O
- Background tasks via FastAPI BackgroundTasks (not Celery yet)
- Static file serving via FastAPI StaticFiles mount

### AI Models
- Virtual Try-On: CatVTON (zhengchong/CatVTON on HuggingFace) via diffusers
- Scene Generation: Provider abstraction layer supporting Flux (fal.ai), GPT Image (OpenAI), SDXL (local diffusers), and a Mock provider for development

### Storage
- Local filesystem (uploads/ and outputs/ directories)
- In-memory job store (with Redis option for production)

### Containerisation
- Dockerfile per service (multi-stage build, non-root user)
- docker-compose.yml at project root

---

## FOLDER STRUCTURE

```
wedding-tryon/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                      # FastAPI app factory, lifespan, router registration, static mount, /health
│   │   ├── config.py                    # Pydantic Settings class reading all env vars, cached singleton via @lru_cache
│   │   ├── dependencies.py             # FastAPI DI — get_local_storage(), get_job_store(), get_image_service(), get_tryon_service(), get_scene_service() — all @lru_cache singletons
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── middleware.py            # CORS setup + global exception handlers mapping custom errors to HTTP codes
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       ├── upload.py            # POST /api/upload — multipart form, validates, saves, creates Job
│   │   │       ├── tryon.py             # POST /api/tryon — guards state, fires TryOnService as BackgroundTask
│   │   │       ├── scene.py             # POST /api/scene — guards state, fires SceneService as BackgroundTask, optional provider override
│   │   │       └── status.py            # GET  /api/status/{job_id} — returns JobStatusResponse with image URLs
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── image_service.py         # Validate uploads (size+type), normalise to PNG via PIL, save/load helpers, resize_for_model
│   │   │   ├── tryon_service.py         # Load CatVTON (cached singleton), offload inference to thread pool, mock fallback when CATVTON_MODEL_ID=mock
│   │   │   └── scene_service.py         # Build Indian wedding prompt, delegate to SceneProvider, update job state
│   │   │
│   │   ├── providers/                   # ← Provider abstraction layer (Strategy pattern)
│   │   │   ├── __init__.py
│   │   │   ├── base.py                  # SceneProviderBase ABC with: name property, async generate(prompt, base_image) -> PIL.Image, validate_config()
│   │   │   ├── factory.py              # create_scene_provider(override?) reads SCENE_PROVIDER env, lazy imports, returns instance
│   │   │   ├── mock_provider.py         # Gradient image + text overlay + pasted try-on thumb. No API keys. Default for dev.
│   │   │   ├── flux_provider.py         # Flux via fal.ai async API. Requires FLUX_API_KEY.
│   │   │   ├── gpt_image_provider.py    # OpenAI gpt-image-1. Requires OPENAI_API_KEY. Uses b64_json response.
│   │   │   └── sdxl_provider.py         # Local SDXL via diffusers img2img. Cached pipeline. Thread pool executor.
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── job.py                   # Job dataclass: job_id, status, timestamps, file paths, error_message. Methods: touch(), mark_failed()
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── job.py                   # Pydantic v2 schemas: JobStatus enum, SceneProvider enum, UploadResponse, TryOnRequest/Response, SceneRequest/Response, JobStatusResponse, ErrorResponse
│   │   │
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── local_storage.py         # LocalStorageService: path helpers, async save_upload/save_output/read_file, delete_job_files. Swap for S3 adapter later.
│   │   │   └── job_store.py             # JobStoreBase ABC, InMemoryJobStore (thread-safe dict), RedisJobStore (JSON serialised, 24h TTL), create_job_store() factory
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── errors.py               # Exception hierarchy: AppError > StorageError/ValidationError/JobNotFoundError/TryOnError/SceneGenerationError/ProviderNotConfiguredError etc.
│   │       ├── logger.py               # structlog setup: setup_logging() at startup, get_logger(name) for modules. ConsoleRenderer in dev, JSONRenderer in prod.
│   │       └── image_utils.py          # Stateless PIL helpers: bytes_to_pil, pil_to_bytes, resize_for_model(max_dim=1024), validate_image_bytes, save_pil_to_path
│   │
│   ├── uploads/                         # Raw uploaded files (gitignored)
│   ├── outputs/                         # Generated images (gitignored)
│   ├── .env.example                     # All env vars with descriptions
│   ├── .env                             # Local copy (gitignored)
│   ├── requirements.txt
│   ├── Dockerfile                       # Multi-stage, non-root user, healthcheck
│   └── docker-compose.yml
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx                     # React entry
│   │   ├── App.tsx                      # Layout shell, step routing
│   │   ├── components/
│   │   │   ├── UploadPanel/
│   │   │   │   ├── ImageDropzone.tsx    # Drag-drop zone with preview, file type/size validation
│   │   │   │   └── UploadPanel.tsx      # Two dropzones side-by-side (person + dress), submit button
│   │   │   ├── ProgressStepper/
│   │   │   │   └── ProgressStepper.tsx  # 4-step visual: Upload → Try-On → Scene → Done. Highlights active step.
│   │   │   └── ResultViewer/
│   │   │       ├── TryOnPreview.tsx     # Displays try-on result image
│   │   │       └── ScenePreview.tsx     # Displays final scene image + download button
│   │   ├── hooks/
│   │   │   ├── useFileUpload.ts         # Manages upload state, calls POST /api/upload, returns job_id
│   │   │   └── useJobPoller.ts          # Polls GET /api/status/{job_id} every 2s, returns current JobStatus + URLs, stops on done/failed
│   │   ├── api/
│   │   │   └── client.ts               # Axios instance with VITE_API_BASE_URL, typed wrappers for all 4 endpoints
│   │   └── types/
│   │       └── index.ts                # TypeScript interfaces matching backend schemas
│   │
│   ├── .env.example                     # VITE_API_BASE_URL=http://localhost:8000
│   ├── index.html
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── package.json
│   └── Dockerfile
│
└── docker-compose.yml                   # Full-stack compose (backend + frontend + optional redis)
```

---

## API CONTRACTS

### POST /api/upload
```
Content-Type: multipart/form-data
Body:
  person_image: File (required) — customer's full-body photo
  dress_image:  File (required) — wedding dress image

Response 202 Accepted:
{
  "job_id": "uuid4-string",
  "status": "queued",
  "message": "Files uploaded successfully. Call /api/tryon to start processing."
}

Error 422: validation errors (file too large, unsupported type)
```

### POST /api/tryon
```
Content-Type: application/json
Body:
{
  "job_id": "uuid4-string"
}

Response 202 Accepted:
{
  "job_id": "uuid4-string",
  "status": "tryon_processing",
  "message": "Virtual try-on started. Poll /api/status/{job_id} for updates."
}

Error 404: job not found
Error 409: wrong job status (must be "queued")
```

### POST /api/scene
```
Content-Type: application/json
Body:
{
  "job_id": "uuid4-string",
  "provider": "flux" | "gpt_image" | "sdxl" | "mock" | null  // optional override
}

Response 202 Accepted:
{
  "job_id": "uuid4-string",
  "status": "scene_processing",
  "message": "Scene generation started. Poll /api/status/{job_id} for updates."
}

Error 404: job not found
Error 409: wrong job status (must be "tryon_done")
```

### GET /api/status/{job_id}
```
Response 200:
{
  "job_id": "uuid4-string",
  "status": "queued" | "tryon_processing" | "tryon_done" | "scene_processing" | "done" | "failed",
  "tryon_url": "/api/images/{job_id}/tryon_result.png" | null,
  "scene_url": "/api/images/{job_id}/scene_result.png" | null,
  "error": "human-readable error string" | null
}

Error 404: job not found
```

### GET /api/images/{job_id}/{filename}
Static file serving from outputs/ directory via FastAPI StaticFiles mount.

### GET /health
```
Response 200: { "status": "ok", "env": "development" }
```

---

## DATA FLOW (step by step)

1. User selects person photo + dress image in the React UI
2. Frontend POSTs to /api/upload (multipart/form-data)
3. Backend validates images (size ≤ 10MB, type in jpeg/png/webp), normalises to PNG, saves to uploads/{job_id}/person.png and dress.png
4. Backend creates Job in job store with status=queued, returns job_id
5. Frontend calls POST /api/tryon with the job_id
6. Backend fires TryOnService.run_tryon() as a BackgroundTask
7. TryOnService loads person + dress images, runs CatVTON inference (offloaded to thread pool), saves result to outputs/{job_id}/tryon_result.png, updates job status to tryon_done
8. Frontend (polling GET /api/status/{job_id} every 2s) detects tryon_done, shows try-on preview, then calls POST /api/scene
9. Backend fires SceneService.run_scene_generation() as a BackgroundTask
10. SceneService loads try-on result, builds Indian wedding prompt, calls the configured SceneProvider.generate(), saves result to outputs/{job_id}/scene_result.png, updates job status to done
11. Frontend detects done, displays final scene image with download button

---

## ENVIRONMENT VARIABLES (.env)

```bash
# Server
APP_ENV=development          # development | production | test
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=DEBUG

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Storage
STORAGE_ROOT=.               # base path; uploads/ and outputs/ are subdirs
UPLOADS_DIR=uploads
OUTPUTS_DIR=outputs
MAX_IMAGE_SIZE_MB=10
ALLOWED_IMAGE_TYPES=image/jpeg,image/png,image/webp

# Virtual Try-On
CATVTON_MODEL_ID=zhengchong/CatVTON    # set to "mock" for dev without GPU
CATVTON_DEVICE=cpu                       # cpu | cuda | mps
HF_TOKEN=hf_YOUR_TOKEN_HERE

# Scene Generation
SCENE_PROVIDER=mock                      # mock | flux | gpt_image | sdxl
FLUX_API_KEY=
FLUX_MODEL_ID=black-forest-labs/FLUX.1-schnell
OPENAI_API_KEY=
OPENAI_IMAGE_MODEL=gpt-image-1
OPENAI_IMAGE_SIZE=1024x1024
SDXL_MODEL_ID=stabilityai/stable-diffusion-xl-base-1.0
SDXL_DEVICE=cpu

# Job Store
JOB_STORE_BACKEND=memory                 # memory | redis
REDIS_URL=redis://localhost:6379/0

# Prompt
SCENE_PROMPT_TEMPLATE=A realistic Indian wedding scene. The bride is wearing the outfit shown in the image. Elegant mandap stage with marigold and rose floral arrangements, draped fabric canopy in gold and red, diyas and string lights, cinematic soft lighting, luxury wedding ambiance, photorealistic, 4k, professional wedding photography style.
```

Frontend .env:
```bash
VITE_API_BASE_URL=http://localhost:8000
```

---

## KEY ARCHITECTURAL PATTERNS

### 1. Provider Abstraction (Strategy Pattern)
All scene generation providers implement `SceneProviderBase`:
```python
class SceneProviderBase(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def generate(self, prompt: str, base_image: Image.Image) -> Image.Image: ...

    def validate_config(self) -> None: ...  # optional, called at construction
```
Factory function `create_scene_provider(override?)` reads env and returns the right implementation. All provider imports are lazy.

### 2. Storage Abstraction
`LocalStorageService` handles all file I/O. Path construction is centralised. To switch to S3/GCS: implement the same interface, swap in dependencies.py.

### 3. Job State Machine
```
queued → tryon_processing → tryon_done → scene_processing → done
  ↓            ↓                              ↓
failed       failed                         failed
```
Each route guards against invalid transitions (e.g. can't start scene if try-on isn't done).

### 4. Background Processing
Try-on and scene generation run via `FastAPI BackgroundTasks`. Each background task has top-level try/except that marks the job as FAILED on any unhandled error. Blocking inference (torch) is offloaded to `asyncio.run_in_executor(None, ...)`.

### 5. Dependency Injection
All services are instantiated via `@lru_cache` singletons in `dependencies.py`. Routes use `Depends(get_*service*)` — never construct services directly.

### 6. Error Handling
Custom exception hierarchy in `utils/errors.py`. Global exception handlers in `middleware.py` map each error type to the correct HTTP status code. Catch-all handler for unexpected errors returns 500 with generic message.

### 7. Logging
structlog configured at startup. Dev = coloured console output. Prod = JSON for log aggregation. All modules use `get_logger(__name__)`.

---

## REQUIREMENTS (backend/requirements.txt)

```
fastapi==0.111.0
uvicorn[standard]==0.30.1
python-multipart==0.0.9
pydantic==2.7.1
pydantic-settings==2.3.1
python-dotenv==1.0.1
Pillow==10.3.0
httpx==0.27.0
aiofiles==23.2.1
torch==2.3.0
torchvision==0.18.0
diffusers==0.27.2
transformers==4.41.1
accelerate==0.30.0
huggingface-hub==0.23.1
openai==1.30.1
redis==5.0.4
structlog==24.1.0
pytest==8.2.1
pytest-asyncio==0.23.7
```

---

## FRONTEND REQUIREMENTS (package.json deps)

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "axios": "^1.7.0",
    "react-dropzone": "^14.2.0",
    "lucide-react": "^0.400.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.5.0",
    "vite": "^5.3.0"
  }
}
```

---

## INSTRUCTIONS FOR CLAUDE CODE

1. Generate the COMPLETE backend first (all files listed above) with production-quality code, type hints, docstrings, and error handling.
2. Then generate the COMPLETE frontend with TypeScript, Tailwind CSS, proper component decomposition, and loading/error states.
3. Use the EXACT folder structure shown above.
4. All services must be injected via FastAPI Depends — no direct instantiation in routes.
5. All providers must implement SceneProviderBase and be registered in the factory.
6. The mock provider must work out-of-the-box with zero API keys so the full pipeline is testable immediately.
7. The CatVTON service must support CATVTON_MODEL_ID=mock for development without GPU/model download.
8. Frontend must poll /api/status/{job_id} every 2 seconds and update the stepper + previews reactively.
9. Frontend must have proper drag-and-drop with file validation (type + size) before upload.
10. Include Dockerfiles for both services and a root docker-compose.yml.
11. Include .env.example files for both backend and frontend.
12. All code must be production-style: no placeholders, no TODOs, no "implement later" comments.

---

## HOW TO RUN LOCALLY

```bash
# Backend
cd backend
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# Swagger UI at http://localhost:8000/docs

# Frontend
cd frontend
cp .env.example .env
npm install
npm run dev
# App at http://localhost:5173

# Docker (full stack)
docker-compose up --build
```
