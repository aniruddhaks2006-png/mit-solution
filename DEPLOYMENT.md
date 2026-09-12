# Deployment Guide

This guide covers how to set up, run, and deploy the MIT Solution hackathon projects locally and in production.

---

## Table of Contents

1. [Local Development](#local-development)
2. [Docker Deployment](#docker-deployment)
3. [Production Checklist](#production-checklist)
4. [Troubleshooting](#troubleshooting)

---

## Local Development

### Prerequisites

- **Python 3.10+**
- **Node.js 16+** and npm (for Problem 2 frontend)
- **Git**

### Problem 1: The Vanishing Dose (Streamlit)

#### Setup

```bash
cd "health care/problem 1 solution"

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate      # macOS/Linux
# or
venv\Scripts\activate          # Windows

# Install dependencies
pip install -r requirements.txt
```

#### Run

```bash
streamlit run app.py
```

The dashboard will open at `http://localhost:8501`

#### Configuration

Create `.streamlit/config.toml` in the problem directory (optional):

```toml
[theme]
primaryColor = "#0066cc"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"

[server]
port = 8501
headless = true
```

---

### Problem 2: Medicine Shortage Early Warning System

#### 2A. Backend (FastAPI)

```bash
cd "health care/problem 2 solution/backend"

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate      # macOS/Linux
# or
venv\Scripts\activate          # Windows

# Install dependencies
pip install -r requirements.txt

# Generate synthetic data
python data_generator.py

# Start server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend API runs at `http://localhost:8000`

**Available endpoints:**
- `GET /` – API root
- `GET /docs` – Swagger UI documentation
- `GET /facilities` – List all facilities
- `GET /medicines` – List all medicines
- `GET /analytics/overview` – System metrics
- `GET /shortages` – Shortage alerts
- `GET /facility/{facility_id}` – Facility details
- `GET /redistribution/{medicine_id}` – Redistribution recommendations

#### 2B. Frontend (React + Vite)

In a **separate terminal**:

```bash
cd "health care/problem 2 solution/frontend"

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend runs at the URL shown in the terminal (typically `http://localhost:5173`)

#### Configuration

Create `.env.local` in the frontend directory:

```
VITE_API_URL=http://localhost:8000
```

---

## Docker Deployment

### Prerequisites

- **Docker** installed and running
- **Docker Compose** (optional, for multi-container setup)

### Problem 1: Streamlit (Single Container)

Create `Dockerfile` in `health care/problem 1 solution/`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Build and run:

```bash
docker build -t vanishing-dose:latest .
docker run -p 8501:8501 vanishing-dose:latest
```

Access at `http://localhost:8501`

---

### Problem 2: Full Stack (Docker Compose)

Create `docker-compose.yml` in `health care/problem 2 solution/`:

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
    command: uvicorn main:app --host 0.0.0.0 --port 8000
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    environment:
      - VITE_API_URL=http://backend:8000
    command: npm run dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
    depends_on:
      - backend

volumes:
  backend-data:
```

#### Backend Dockerfile

Create `health care/problem 2 solution/backend/Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Frontend Dockerfile

Create `health care/problem 2 solution/frontend/Dockerfile`:

```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
```

#### Run with Docker Compose

```bash
cd "health care/problem 2 solution"
docker-compose up --build
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`

---

## Production Checklist

### Security

- [ ] Replace `.env.example` values with real secrets
- [ ] Use environment variables for all configuration
- [ ] Enable HTTPS (use reverse proxy like Nginx)
- [ ] Implement authentication/authorization
- [ ] Set up secrets management (AWS Secrets Manager, HashiCorp Vault, etc.)
- [ ] Enable CORS properly (don't allow `*` in production)

### Data Management

- [ ] Replace synthetic data with real data sources
- [ ] Set up persistent database (PostgreSQL, MongoDB, etc.)
- [ ] Implement data validation and sanitization
- [ ] Add backup and recovery procedures
- [ ] Comply with data privacy regulations (HIPAA, GDPR, etc.)

### Monitoring & Logging

- [ ] Set up centralized logging (ELK Stack, DataDog, etc.)
- [ ] Add application performance monitoring (APM)
- [ ] Configure alerts for errors and anomalies
- [ ] Log all API requests and responses
- [ ] Implement audit trails for compliance

### Deployment

- [ ] Use container orchestration (Kubernetes, Docker Swarm)
- [ ] Set up CI/CD pipeline (GitHub Actions, GitLab CI, etc.)
- [ ] Configure load balancing
- [ ] Implement health checks and auto-restart
- [ ] Use semantic versioning for releases
- [ ] Document rollback procedures

### API

- [ ] Add rate limiting
- [ ] Implement request validation (Pydantic for FastAPI)
- [ ] Add API versioning strategy
- [ ] Document all endpoints (OpenAPI/Swagger)
- [ ] Add request/response compression

### Database

- [ ] Index frequently queried columns
- [ ] Set up connection pooling
- [ ] Implement caching (Redis)
- [ ] Monitor query performance
- [ ] Regular backup and verification

### Frontend

- [ ] Minify and optimize assets
- [ ] Implement lazy loading
- [ ] Add error boundary and fallback UI
- [ ] Test across browsers and devices
- [ ] Set up CDN for static assets

---

## Troubleshooting

### Problem 1: Streamlit

**Issue: Port 8501 already in use**
```bash
streamlit run app.py --server.port 8502
```

**Issue: ModuleNotFoundError**
```bash
pip install -r requirements.txt --upgrade
```

**Issue: Dashboard not loading**
- Clear cache: `streamlit cache clear`
- Check logs: `streamlit run app.py --logger.level=debug`

---

### Problem 2: Backend (FastAPI)

**Issue: Port 8000 already in use**
```bash
uvicorn main:app --port 8001
```

**Issue: ModuleNotFoundError**
```bash
pip install -r requirements.txt --upgrade
```

**Issue: data_generator.py not creating data**
```bash
python data_generator.py --verbose
# Check that output file is created in the working directory
```

**Issue: API returns 500 error**
- Check backend logs for stack trace
- Ensure `data_generator.py` was run before starting server
- Verify environment variables in `.env`

---

### Problem 2: Frontend (React)

**Issue: Cannot connect to backend**
- Ensure backend is running on the correct port
- Check `VITE_API_URL` environment variable
- Verify CORS is enabled on backend

**Issue: npm install fails**
```bash
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

**Issue: Hot reload not working**
- Ensure `npm run dev` is used (not `npm run build`)
- Check that Vite config has correct host/port

---

### Docker Issues

**Issue: Container exits immediately**
```bash
docker logs <container_id>  # View error messages
```

**Issue: Port conflicts**
```bash
docker-compose down  # Stop all containers
docker system prune    # Clean up unused images/containers
```

---

## Performance Tuning

### Backend (FastAPI)

```python
# main.py
from fastapi import FastAPI
from fastapi.middleware.gzip import GZIPMiddleware

app = FastAPI()
app.add_middleware(GZIPMiddleware, minimum_size=1000)
```

### Frontend (React)

```js
// vite.config.js
import react from '@vitejs/plugin-react'

export default {
  plugins: [react()],
  build: {
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
      },
    },
  },
}
```

---

## Support

For deployment issues, refer to:
- [Streamlit Docs](https://docs.streamlit.io)
- [FastAPI Docs](https://fastapi.tiangolo.com)
- [Vite Docs](https://vitejs.dev)
- [Docker Docs](https://docs.docker.com)

See `CONTRIBUTING.md` for how to report issues.
