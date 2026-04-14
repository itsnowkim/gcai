# GCAI

GCAI is a graph-based code understanding service that scans a repository, extracts symbols and relations, and stores them in Neo4j and ChromaDB.

## Requirements

- Python 3.11+
- Docker Desktop
- Docker Compose

## Local setup

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
py -3.13 -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

## Run the API

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```powershell
curl http://localhost:8000/health
```

## Docker stack

Start Neo4j and ChromaDB:

```powershell
docker compose up -d neo4j chroma
```

Run the full app stack:

```powershell
docker compose up --build
```

Default ports:

- API: 8000
- Neo4j HTTP: 7474
- Neo4j Bolt: 7687
- ChromaDB: 8001

## Initial indexing

Run the initial index against the current repository:

```powershell
python -m app.cli.index_codebase . --pretty
```

The JSON result includes both inserted counts and `verified_*` fields that confirm the stored Neo4j and ChromaDB counts after the run.

## Tests

```powershell
py -3.13 -m pytest -q tests
```
