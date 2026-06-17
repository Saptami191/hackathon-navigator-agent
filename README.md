# Hackathon Navigator Agent

A full-stack application for discovering hackathon opportunities with AI-powered agent support.

## Project Structure

```
hackathon-navigator-agent/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/               # API routes
│   │   ├── core/              # Core functionality (auth, config)
│   │   ├── services/          # Business logic services
│   │   ├── agents/            # AI agent implementations
│   │   └── main.py            # Application entry point
│   ├── Dockerfile
│   ├── pyproject.toml         # Python dependencies
│   └── .env.example
│
├── frontend/                  # Next.js frontend
│   ├── src/
│   │   ├── app/               # Next.js app directory
│   │   ├── components/        # React components
│   │   ├── hooks/             # Custom React hooks
│   │   ├── lib/               # Utilities and helpers
│   │   └── providers/         # Context providers
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   └── .env.local.example
│
└── docker-compose.yml         # Local development orchestration
```

## Prerequisites

- **Backend**: Python 3.11+, Poetry
- **Frontend**: Node.js 20+, npm or yarn
- **Optional**: Docker and Docker Compose

## Local Setup

### Backend

1. Change into the backend directory:
   ```bash
   cd backend
   ```

2. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

3. Install dependencies:
   ```bash
   poetry install
   ```

4. Start the backend in development mode:
   ```bash
   poetry run uvicorn app.main:app --reload
   ```

- Backend API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Frontend

1. Change into the frontend directory:
   ```bash
   cd frontend
   ```

2. Copy the example environment file:
   ```bash
   cp .env.local.example .env.local
   ```

3. Install dependencies:
   ```bash
   npm install
   ```

4. Start the frontend:
   ```bash
   npm run dev
   ```

- Frontend app: `http://localhost:3000`

## Docker Setup

Use Docker Compose to run the full stack with PostgreSQL and Redis:

```bash
docker-compose up -d
```

Services:
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

Useful commands:

```bash
# Follow logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild services
docker-compose up --build -d
```

## Available Scripts

### Backend

```bash
poetry run uvicorn app.main:app --reload
poetry run pytest
poetry run ruff .
poetry run mypy app
```

### Frontend

```bash
npm run dev
npm run build
npm run start
npm run lint
npm run type-check
```

## Environment Variables

### Backend (`backend/.env`)
- `ENVIRONMENT` - app environment, e.g. `development` or `production`
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `GITHUB_TOKEN` - GitHub API token
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- `SECRET_KEY` - JWT secret for auth
- `CORS_ORIGINS` - allowed frontend origins

### Frontend (`frontend/.env.local`)
- `NEXT_PUBLIC_API_BASE_URL` - backend API URL
- `NEXT_PUBLIC_API_VERSION` - API version
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` - Clerk publishable key

Refer to `backend/.env.example` and `frontend/.env.local.example` for full examples.

## Development Notes

- Python backend is built with FastAPI, SQLAlchemy, Celery, and async services.
- Frontend uses Next.js 15, React 18, Tailwind CSS, Clerk auth, and React Query.

## Testing

```bash
# Backend tests
cd backend && poetry run pytest

# Frontend type check
cd frontend && npm run type-check
```

## Deployment

Build images for production:

```bash
docker build -t hackathon-nav-backend:latest ./backend
docker build -t hackathon-nav-frontend:latest ./frontend
```

For production, update environment variables and run with your preferred container orchestration or cloud provider.

- `backend/.env`
- `frontend/.env.local`

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Commit changes: `git commit -m 'Add your feature'`
3. Push to branch: `git push origin feature/your-feature`
4. Open a Pull Request

## Tech Stack

### Backend
- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy
- **Cache**: Redis
- **Task Queue**: Celery
- **LLM**: OpenAI, Anthropic
- **Graph**: LangGraph
- **VCS**: PyGithub, GitPython

### Frontend
- **Framework**: Next.js 15
- **UI**: React 18 with Radix UI components
- **Styling**: Tailwind CSS
- **State**: Zustand
- **Data Fetching**: TanStack Query (React Query)
- **Forms**: React Hook Form + Zod validation
- **Auth**: Clerk
- **Charts**: Recharts

## License

MIT

## Support

For issues and questions, please open an issue on GitHub.