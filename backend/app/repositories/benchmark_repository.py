from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import BenchmarkCase, BenchmarkSuite


class BenchmarkRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_suite(
        self,
        name: str,
        description: str | None = None,
        version: str = "v1",
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> BenchmarkSuite:
        suite = BenchmarkSuite(
            name=name,
            description=description,
            version=version,
            tags=tags or [],
            metadata=metadata or {},
        )
        self.session.add(suite)
        await self.session.commit()
        await self.session.refresh(suite)
        return suite

    async def get_suite(self, suite_id: str | None = None, name: str | None = None) -> BenchmarkSuite | None:
        query = select(BenchmarkSuite)
        if suite_id:
            query = query.where(BenchmarkSuite.id == suite_id)
        elif name:
            query = query.where(BenchmarkSuite.name == name)
        else:
            return None
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_suites(self) -> list[BenchmarkSuite]:
        result = await self.session.execute(select(BenchmarkSuite).order_by(BenchmarkSuite.created_at.desc()))
        return result.scalars().all()

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
        benchmark_case = BenchmarkCase(
            suite_id=suite_id,
            title=title,
            description=description,
            repository_state=repository_state or {},
            team_status=team_status or {},
            deadlines=deadlines or {},
            expected_actions=expected_actions or {},
            ground_truth=ground_truth or {},
            tags=tags or [],
            case_version=case_version,
        )
        self.session.add(benchmark_case)
        await self.session.commit()
        await self.session.refresh(benchmark_case)
        return benchmark_case

    async def list_cases(self, suite_id: str) -> list[BenchmarkCase]:
        result = await self.session.execute(
            select(BenchmarkCase)
            .where(BenchmarkCase.suite_id == suite_id, BenchmarkCase.is_active == True)
            .order_by(BenchmarkCase.created_at)
        )
        return result.scalars().all()

    async def get_case(self, case_id: str) -> BenchmarkCase | None:
        result = await self.session.execute(select(BenchmarkCase).where(BenchmarkCase.id == case_id))
        return result.scalar_one_or_none()
