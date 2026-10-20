## HauSort
A transparent decision engine helps you determine which apartment best matches your priorities.

## Project Structure

```
HauSort/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── __init__.py
│   │   │   │   └── health.py
│   │   │   ├── __init__.py
│   │   │   └── api.py
│   │   └── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py
│   ├── models/             # SQLModel Database Models & Relationships
│   │   ├── __init__.py
│   │   ├── ad_source.py
│   │   ├── base.py
│   │   ├── comparison.py
│   │   ├── comparison_ad.py
│   │   ├── comparison_score_detail.py
│   │   ├── enums.py
│   │   ├── housing_ad.py
│   │   ├── user.py
│   │   └── user_preference.py
│   ├── schemas/            # Pydantic validation schemas
│   ├── services/           # Business logic & external services
│   ├── __init__.py
│   └── main.py             # FastAPI entrypoint
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
└── README.md
```

## Getting Started with `uv`

### 1. Sync Dependencies
```bash
uv sync
```

### 2. Run the Development Server
Using FastAPI CLI:
```bash
uv run fastapi dev app/main.py
```
Or using Uvicorn directly:
```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Adding New Packages
```bash
uv add <package_name>
```

## Running with Docker

### Using Docker Compose (Dev with Hot-Reload)
```bash
docker compose up --build
```
To run in the background:
```bash
docker compose up -d
```
To stop the containers:
```bash
docker compose down
```

### Using Docker directly
```bash
docker build -t hausort-api .
docker run -p 8000:8000 hausort-api
```

## Interactive API Docs & Endpoints

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Health check: `GET http://localhost:8000/api/v1/health`

### Scraping Endpoints

- `POST /api/v1/scrape-jobs`: Scrapes up to 10 listing URLs with SSRF validation, parses structured metadata, and persists normalized ads.
  ```json
  {
    "urls": [
      "https://www.wg-gesucht.de/wg-zimmer-in-Trier.12345.html"
    ]
  }
  ```
- `POST /api/v1/housing-ads/from-text`: First-class fallback to submit pasted ad text.
  ```json
  {
    "title": "WG room Trier",
    "raw_text": "Warmmiete: 450 Euro. Kaution: 800 Euro. Anmeldung möglich. 18 qm.",
    "source_url": "https://example.com/ad"
  }
  ```
- `GET /api/v1/housing-ads/{ad_id}`: Retrieve normalized ad details and extraction status.

## Running Tests

```bash
uv run pytest tests
```

