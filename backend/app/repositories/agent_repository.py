from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentVersion


class AgentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_version(
        self,
        name: str,
        version: str,
        callable_path: str,
        branch: str | None = None,
        description: str | None = None,
        metadata: dict | None = None,
        status: str = "active",
    ) -> AgentVersion:
        agent = AgentVersion(
            name=name,
            version=version,
            callable_path=callable_path,
            branch=branch,
            description=description,
            metadata=metadata or {},
            status=status,
        )
        self.session.add(agent)
        await self.session.commit()
        await self.session.refresh(agent)
        return agent

    async def list_versions(self) -> list[AgentVersion]:
        result = await self.session.execute(
            select(AgentVersion).where(AgentVersion.is_active == True).order_by(AgentVersion.created_at.desc())
        )
        return result.scalars().all()

    async def get_version(self, agent_version_id: str) -> AgentVersion | None:
        result = await self.session.execute(select(AgentVersion).where(AgentVersion.id == agent_version_id))
        return result.scalar_one_or_none()

    async def get_latest_by_name(self, name: str) -> AgentVersion | None:
        result = await self.session.execute(
            select(AgentVersion)
            .where(AgentVersion.name == name, AgentVersion.is_active == True)
            .order_by(AgentVersion.created_at.desc())
        )
        return result.scalar_one_or_none()
