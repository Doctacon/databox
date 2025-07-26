# Docker Setup for Databox

This directory contains Docker configurations for running Databox in containerized environments.

## Quick Start

### Development Environment

```bash
# Start development environment with hot reloading
task docker:dev

# Or manually:
docker-compose -f docker-compose.dev.yml up -d
docker-compose -f docker-compose.dev.yml exec dev bash
```

### Production Environment

```bash
# Build and start all services
task docker:build
task docker:up

# View logs
task docker:logs

# Stop services
task docker:down
```

## Available Services

### Default Stack (docker-compose.yml)
- **databox**: Main application with Dagster UI (port 3000)
- **jupyter**: Jupyter Lab for analysis (port 8888)
- **sqlmesh**: SQLMesh UI (port 8000)

### Optional Services (use profiles)
- **postgres**: PostgreSQL database (profile: postgres)
- **minio**: S3-compatible storage (profile: cloud)

```bash
# Start with PostgreSQL
docker-compose --profile postgres up -d

# Start with MinIO
docker-compose --profile cloud up -d
```

### Development Stack (docker-compose.dev.yml)
- **dev**: Development container with mounted source
- **duckdb**: DuckDB with HTTP API
- **adminer**: Database UI (port 8080)
- **taskrunner**: Auto-running tasks (profile: watch)

## Configuration

### Environment Variables
Create a `.env` file with:
```env
EBIRD_API_TOKEN=your_token_here
DATABASE_URL=duckdb:///app/data/databox.db
```

### Volumes
- `./data`: Persistent data storage
- `./logs`: Application logs
- `./notebooks`: Jupyter notebooks

## Docker Images

### Production Image (Dockerfile)
- Based on `python:3.12-slim-bookworm`
- Non-root user for security
- Minimal dependencies
- Optimized for size (~500MB)

### Development Image (Dockerfile.dev)
- Includes development tools (vim, htop, ipython)
- Hot reloading support
- Debug utilities
- Full dependency set

## Common Tasks

### Access Running Container
```bash
docker-compose exec databox bash
```

### Run DLT Pipeline
```bash
docker-compose exec databox python pipelines/sources/ebird_api.py
```

### Run SQLMesh Transformations
```bash
docker-compose exec databox bash -c "cd transformations/home_team && sqlmesh run"
```

### Access Jupyter
Open http://localhost:8888 (no password required in dev)

### View Dagster UI
Open http://localhost:3000

## Troubleshooting

### Permission Issues
If you encounter permission errors:
```bash
# Fix ownership
docker-compose exec --user root databox chown -R databox:databox /app/data
```

### Database Connection
The default uses DuckDB at `/app/data/databox.db`. For PostgreSQL:
```bash
DATABASE_URL=postgresql://databox:databox@postgres:5432/databox
```

### Memory Issues
Increase Docker memory allocation in Docker Desktop settings or use:
```yaml
services:
  databox:
    deploy:
      resources:
        limits:
          memory: 4G
```

## Security Notes

1. The production image runs as non-root user `databox`
2. Secrets should be passed via environment variables or Docker secrets
3. The development image has no authentication on Jupyter (don't expose publicly)
4. Consider using Docker secrets for production deployments