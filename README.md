# Hackathon Navigator Agent

A full-stack application for navigating and discovering hackathon opportunities with AI-powered agent support.

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
- **Frontend**: Node.js 20+, npm/yarn
- **Docker** (optional, for containerized setup)

## Setup & Installation

### Backend Setup

1. Navigate to backend directory:
   ```bash
   cd backend
   ```

2. Create environment file:
   ```bash
   cp .env.example .env
   ```

3. Install dependencies:
   ```bash
   poetry install
   ```

4. Start the backend server:
   ```bash
   poetry run uvicorn app.main:app --reload
   ```

The API will be available at `http://localhost:8000`

API Documentation: `http://localhost:8000/docs` (Swagger UI)

### Frontend Setup

1. Navigate to frontend directory:
   ```bash
   cd frontend
   ```

2. Create environment file:
   ```bash
   cp .env.local.example .env.local
   ```

3. Install dependencies:
   ```bash
   npm install
   # or
   yarn install
   ```

4. Start the development server:
   ```bash
   npm run dev
   # or
   yarn dev
   ```

The app will be available at `http://localhost:3000`

## Docker Setup (Recommended for Development)

Run both services with all dependencies using Docker Compose:

```bash
docker-compose up -d
```

This will start:
- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:3000
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### Useful Docker Commands

```bash
# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild services
docker-compose up --build
```

## Available Scripts

### Backend

```bash
poetry run uvicorn app.main:app --reload    # Development server
poetry run pytest                            # Run tests
poetry run black .                           # Code formatting
poetry run mypy app                          # Type checking
poetry run flake8 app                        # Linting
```

### Frontend

```bash
npm run dev          # Development server
npm run build        # Production build
npm run start        # Start production server
npm run lint         # Run ESLint
npm run type-check   # TypeScript type checking
```

## Environment Variables

### Backend (.env)
- `ENVIRONMENT`: Development/production
- `DATABASE_URL`: PostgreSQL connection string
- `GITHUB_TOKEN`: GitHub API token
- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key

### Frontend (.env.local)
- `NEXT_PUBLIC_API_BASE_URL`: Backend API URL
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`: Clerk authentication key

See `.env.example` and `.env.local.example` for complete configurations.

## API Documentation

Once the backend is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Development

### Code Style

- **Python**: Black, Flake8, MyPy
- **TypeScript/JavaScript**: ESLint, Prettier
- **CSS**: Tailwind CSS

### Testing

```bash
# Backend tests
cd backend && poetry run pytest

# Frontend tests
cd frontend && npm test
```

## Deployment

### Docker Build

```bash
# Build backend
docker build -t hackathon-nav-backend:latest ./backend

# Build frontend
docker build -t hackathon-nav-frontend:latest ./frontend
```

### Production Environment

Update environment variables for production in:
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