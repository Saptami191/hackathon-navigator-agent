from importlib import import_module
from types import ModuleType

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentVersion
from repositories.agent_repository import AgentRepository


class AgentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AgentRepository(session)

    async def create_agent_version(
        self,
        name: str,
        version: str,
        callable_path: str,
        branch: str | None = None,
        description: str | None = None,
        metadata: dict | None = None,
        status: str = "active",
    ) -> AgentVersion:
        return await self.repo.create_version(
            name=name,
            version=version,
            callable_path=callable_path,
            branch=branch,
            description=description,
            metadata=metadata,
            status=status,
        )

    async def list_agent_versions(self) -> list[AgentVersion]:
        return await self.repo.list_versions()

    async def get_agent_version(self, agent_version_id: str) -> AgentVersion | None:
        return await self.repo.get_version(agent_version_id)

    def load_agent_callable(self, callable_path: str):
        module_name, function_name = callable_path.rsplit(".", 1)
        module: ModuleType = import_module(module_name)
        return getattr(module, function_name)
