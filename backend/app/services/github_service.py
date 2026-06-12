import asyncio
import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import structlog
from github import Auth, Github, GithubException
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class RepoFile:
    path: str
    content: str
    size: int
    sha: str


@dataclass
class CommitInfo:
    sha: str
    message: str
    author: str
    author_email: str
    timestamp: datetime
    additions: int
    deletions: int


@dataclass
class PRInfo:
    number: int
    title: str
    state: str
    author: str
    created_at: datetime
    updated_at: datetime
    labels: list[str]
    review_state: str | None


@dataclass
class IssueInfo:
    number: int
    title: str
    body: str | None
    state: str
    author: str
    labels: list[str]
    created_at: datetime
    is_bug: bool
    is_feature: bool


@dataclass
class RepoAnalysis:
    name: str
    full_name: str
    description: str | None
    default_branch: str
    stars: int
    forks: int
    open_issues_count: int
    languages: dict[str, int]
    topics: list[str]
    readme_content: str | None
    folder_structure: dict[str, Any]
    key_files: list[RepoFile]
    recent_commits: list[CommitInfo]
    open_prs: list[PRInfo]
    open_issues: list[IssueInfo]
    contributors: list[dict[str, Any]]
    inactive_contributors: list[str]
    last_commit_at: datetime | None
    commit_frequency: float  # commits per day (last 7 days)


class GitHubService:
    def __init__(self, token: str | None = None):
        self.token = token or settings.github_token
        self.gh = Github(Auth.Token(self.token))
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            base_url="https://api.github.com",
            timeout=30.0,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def analyze_repository(self, repo_url: str) -> RepoAnalysis:
        repo_name = self._parse_repo_name(repo_url)
        logger.info("Analyzing repository", repo=repo_name)

        try:
            repo = await asyncio.to_thread(self.gh.get_repo, repo_name)

            # Gather all data concurrently
            (
                readme,
                structure,
                key_files,
                commits,
                prs,
                issues,
                contributors,
                languages,
            ) = await asyncio.gather(
                self._get_readme(repo),
                self._get_folder_structure(repo),
                self._get_key_files(repo),
                self._get_recent_commits(repo),
                self._get_open_prs(repo),
                self._get_open_issues(repo),
                self._get_contributors(repo),
                asyncio.to_thread(lambda: dict(repo.get_languages())),
                return_exceptions=True,
            )

            # Handle any exceptions from concurrent gather
            readme = readme if not isinstance(readme, Exception) else None
            structure = structure if not isinstance(structure, Exception) else {}
            key_files = key_files if not isinstance(key_files, Exception) else []
            commits = commits if not isinstance(commits, Exception) else []
            prs = prs if not isinstance(prs, Exception) else []
            issues = issues if not isinstance(issues, Exception) else []
            contributors = contributors if not isinstance(contributors, Exception) else []
            languages = languages if not isinstance(languages, Exception) else {}

            # Calculate commit frequency
            now = datetime.now(timezone.utc)
            week_ago = now - timedelta(days=7)
            recent = [c for c in commits if c.timestamp > week_ago]
            commit_frequency = len(recent) / 7.0

            # Detect inactive contributors
            active_authors = {c.author for c in commits if c.timestamp > week_ago}
            all_contributors = [c.get("login", "") for c in contributors]
            inactive = [c for c in all_contributors if c not in active_authors]

            last_commit = commits[0].timestamp if commits else None

            return RepoAnalysis(
                name=repo.name,
                full_name=repo.full_name,
                description=repo.description,
                default_branch=repo.default_branch,
                stars=repo.stargazers_count,
                forks=repo.forks_count,
                open_issues_count=repo.open_issues_count,
                languages=languages,
                topics=list(repo.get_topics()),
                readme_content=readme,
                folder_structure=structure,
                key_files=key_files,
                recent_commits=commits,
                open_prs=prs,
                open_issues=issues,
                contributors=contributors,
                inactive_contributors=inactive,
                last_commit_at=last_commit,
                commit_frequency=commit_frequency,
            )

        except GithubException as e:
            logger.error("GitHub API error", error=str(e), repo=repo_name)
            raise

    async def _get_readme(self, repo) -> str | None:
        try:
            readme = await asyncio.to_thread(repo.get_readme)
            content = base64.b64decode(readme.content).decode("utf-8", errors="replace")
            return content[:10000]  # Limit size
        except Exception:
            return None

    async def _get_folder_structure(self, repo, path: str = "", depth: int = 0) -> dict[str, Any]:
        if depth > 3:
            return {}
        try:
            contents = await asyncio.to_thread(repo.get_contents, path)
            structure = {}
            dirs = []
            files = []

            for item in contents:
                if item.type == "dir":
                    dirs.append(item.name)
                else:
                    files.append(item.name)

            structure["files"] = files
            structure["dirs"] = {}

            # Only recurse into important directories
            important_dirs = {"src", "app", "api", "components", "lib", "utils", "services", "models", "routes", "agents"}
            for d in dirs:
                if d in important_dirs or depth < 2:
                    sub = await self._get_folder_structure(repo, f"{path}/{d}" if path else d, depth + 1)
                    structure["dirs"][d] = sub
                else:
                    structure["dirs"][d] = {"files": [], "dirs": {}}

            return structure
        except Exception:
            return {}

    async def _get_key_files(self, repo) -> list[RepoFile]:
        important_files = [
            "README.md", "README.rst", "package.json", "requirements.txt",
            "pyproject.toml", "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
            ".env.example", "vercel.json", "railway.json", "Makefile",
            "src/main.py", "app/main.py", "main.py", "index.ts", "src/index.ts",
        ]
        files = []
        for file_path in important_files:
            try:
                content_file = await asyncio.to_thread(repo.get_contents, file_path)
                if content_file.size < 50000:  # Skip large files
                    content = base64.b64decode(content_file.content).decode("utf-8", errors="replace")
                    files.append(RepoFile(
                        path=file_path,
                        content=content[:5000],
                        size=content_file.size,
                        sha=content_file.sha,
                    ))
            except Exception:
                continue
        return files

    async def _get_recent_commits(self, repo, days: int = 30) -> list[CommitInfo]:
        try:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            commits_raw = await asyncio.to_thread(
                lambda: list(repo.get_commits(since=since))[:50]
            )
            commits = []
            for c in commits_raw:
                try:
                    commit = CommitInfo(
                        sha=c.sha[:7],
                        message=c.commit.message[:200],
                        author=c.commit.author.name or "Unknown",
                        author_email=c.commit.author.email or "",
                        timestamp=c.commit.author.date.replace(tzinfo=timezone.utc),
                        additions=c.stats.additions if c.stats else 0,
                        deletions=c.stats.deletions if c.stats else 0,
                    )
                    commits.append(commit)
                except Exception:
                    continue
            return commits
        except Exception:
            return []

    async def _get_open_prs(self, repo) -> list[PRInfo]:
        try:
            prs_raw = await asyncio.to_thread(lambda: list(repo.get_pulls(state="open"))[:20])
            prs = []
            for pr in prs_raw:
                reviews = await asyncio.to_thread(lambda p=pr: list(p.get_reviews())[:5])
                review_state = reviews[-1].state if reviews else None
                prs.append(PRInfo(
                    number=pr.number,
                    title=pr.title,
                    state=pr.state,
                    author=pr.user.login if pr.user else "Unknown",
                    created_at=pr.created_at.replace(tzinfo=timezone.utc),
                    updated_at=pr.updated_at.replace(tzinfo=timezone.utc),
                    labels=[l.name for l in pr.labels],
                    review_state=review_state,
                ))
            return prs
        except Exception:
            return []

    async def _get_open_issues(self, repo) -> list[IssueInfo]:
        try:
            issues_raw = await asyncio.to_thread(
                lambda: list(repo.get_issues(state="open"))[:30]
            )
            issues = []
            for issue in issues_raw:
                if issue.pull_request:
                    continue  # Skip PRs from issues list
                labels = [l.name for l in issue.labels]
                issues.append(IssueInfo(
                    number=issue.number,
                    title=issue.title,
                    body=(issue.body or "")[:500],
                    state=issue.state,
                    author=issue.user.login if issue.user else "Unknown",
                    labels=labels,
                    created_at=issue.created_at.replace(tzinfo=timezone.utc),
                    is_bug=any(l in ["bug", "error", "fix"] for l in labels),
                    is_feature=any(l in ["enhancement", "feature", "feat"] for l in labels),
                ))
            return issues
        except Exception:
            return []

    async def _get_contributors(self, repo) -> list[dict[str, Any]]:
        try:
            contribs = await asyncio.to_thread(lambda: list(repo.get_contributors())[:20])
            return [
                {
                    "login": c.login,
                    "contributions": c.contributions,
                    "avatar_url": c.avatar_url,
                }
                for c in contribs
            ]
        except Exception:
            return []

    def _parse_repo_name(self, url: str) -> str:
        url = url.rstrip("/")
        if "github.com/" in url:
            parts = url.split("github.com/")[-1].split("/")
            return f"{parts[0]}/{parts[1]}"
        return url
        