from sqlalchemy.ext.asyncio import AsyncSession

from db.models import BenchmarkCase, BenchmarkSuite
from repositories.benchmark_repository import BenchmarkRepository


class BenchmarkService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = BenchmarkRepository(session)

    async def create_suite(
        self,
        name: str,
        description: str | None = None,
        version: str = "v1",
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> BenchmarkSuite:
        return await self.repo.create_suite(name, description, version, tags, metadata)

    async def list_suites(self) -> list[BenchmarkSuite]:
        return await self.repo.list_suites()

    async def get_suite(self, suite_id: str) -> BenchmarkSuite | None:
        return await self.repo.get_suite(suite_id=suite_id)

    async def create_case(
        self,
        suite_id: str,
        title: str,
        description: str | None = None,
        repository_state: dict | None = None,
        team_status: dict | None = None,
        deadlines: dict | None = None,
        expected_actions: dict | None = None,
        ground_truth: dict | None = None,
        tags: list[str] | None = None,
        case_version: str | None = None,
    ) -> BenchmarkCase:
        return await self.repo.create_case(
            suite_id=suite_id,
            title=title,
            description=description,
            repository_state=repository_state,
            team_status=team_status,
            deadlines=deadlines,
            expected_actions=expected_actions,
            ground_truth=ground_truth,
            tags=tags,
            case_version=case_version,
        )

    async def list_cases(self, suite_id: str) -> list[BenchmarkCase]:
        return await self.repo.list_cases(suite_id)

    async def get_case(self, case_id: str) -> BenchmarkCase | None:
        return await self.repo.get_case(case_id)
