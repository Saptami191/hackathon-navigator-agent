import hashlib
import uuid
from typing import Any

import structlog
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.models import Distance, PointStruct, VectorParams

from core.config import settings

logger = structlog.get_logger(__name__)


class RAGService:
    """Retrieval-Augmented Generation service backed by Qdrant."""

    def __init__(self):
        self.client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
        self.embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
        )

    async def ensure_collection(self):
        """Create collection if it doesn't exist."""
        try:
            await self.client.get_collection(settings.qdrant_collection)
        except Exception:
            await self.client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(
                    size=settings.embedding_dimension,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection", collection=settings.qdrant_collection)

    async def ingest_repository(self, project_id: str, repo_analysis: Any) -> int:
        """Ingest a full repository analysis into the vector store."""
        await self.ensure_collection()

        documents = []

        # README
        if repo_analysis.readme_content:
            documents.append({
                "content": repo_analysis.readme_content,
                "doc_type": "readme",
                "source": "README.md",
            })

        # Key files
        for file in repo_analysis.key_files:
            documents.append({
                "content": f"File: {file.path}\n\n{file.content}",
                "doc_type": "source_file",
                "source": file.path,
            })

        # Issues
        for issue in repo_analysis.open_issues:
            documents.append({
                "content": f"Issue #{issue.number}: {issue.title}\n{issue.body or ''}",
                "doc_type": "github_issue",
                "source": f"issue_{issue.number}",
            })

        # Structure summary
        structure_text = self._serialize_structure(repo_analysis.folder_structure)
        documents.append({
            "content": f"Repository structure:\n{structure_text}",
            "doc_type": "repo_structure",
            "source": "folder_structure",
        })

        # Commit history
        commit_text = "\n".join([
            f"{c.sha} by {c.author}: {c.message}"
            for c in repo_analysis.recent_commits[:20]
        ])
        documents.append({
            "content": f"Recent commits:\n{commit_text}",
            "doc_type": "commit_history",
            "source": "git_history",
        })

        # Chunk and embed
        points = []
        for doc in documents:
            chunks = self.splitter.split_text(doc["content"])
            texts = chunks if chunks else [doc["content"]]

            embeddings = await self._embed_texts(texts)

            for i, (chunk, embedding) in enumerate(zip(texts, embeddings)):
                point_id = self._generate_point_id(project_id, doc["source"], i)
                points.append(PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "project_id": project_id,
                        "content": chunk,
                        "doc_type": doc["doc_type"],
                        "source": doc["source"],
                        "chunk_index": i,
                    },
                ))

        # Upsert in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            await self.client.upsert(
                collection_name=settings.qdrant_collection,
                points=batch,
            )

        logger.info("Ingested repository into RAG", project_id=project_id, chunks=len(points))
        return len(points)

    async def search(
        self,
        project_id: str,
        query: str,
        top_k: int = settings.rag_top_k,
        doc_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for relevant context given a query."""
        await self.ensure_collection()

        query_embedding = await self._embed_texts([query])
        query_vector = query_embedding[0]

        # Build filter
        filter_conditions = [
            models.FieldCondition(
                key="project_id",
                match=models.MatchValue(value=project_id),
            )
        ]
        if doc_types:
            filter_conditions.append(
                models.FieldCondition(
                    key="doc_type",
                    match=models.MatchAny(any=doc_types),
                )
            )

        results = await self.client.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_vector,
            query_filter=models.Filter(must=filter_conditions),
            limit=top_k,
            with_payload=True,
        )

        return [
            {
                "content": r.payload["content"],
                "doc_type": r.payload.get("doc_type"),
                "source": r.payload.get("source"),
                "score": r.score,
            }
            for r in results
        ]

    async def delete_project_data(self, project_id: str):
        """Remove all vectors for a project."""
        await self.client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="project_id",
                            match=models.MatchValue(value=project_id),
                        )
                    ]
                )
            ),
        )
        logger.info("Deleted project data from RAG", project_id=project_id)

    async def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        return await self.embeddings.aembed_documents(texts)

    def _generate_point_id(self, project_id: str, source: str, chunk_idx: int) -> str:
        key = f"{project_id}:{source}:{chunk_idx}"
        hash_hex = hashlib.md5(key.encode()).hexdigest()
        return str(uuid.UUID(hash_hex))

    def _serialize_structure(self, structure: dict, prefix: str = "", depth: int = 0) -> str:
        if depth > 4 or not structure:
            return ""
        lines = []
        indent = "  " * depth
        for file in structure.get("files", []):
            lines.append(f"{indent}{prefix}{file}")
        for dir_name, sub in structure.get("dirs", {}).items():
            lines.append(f"{indent}{prefix}{dir_name}/")
            lines.append(self._serialize_structure(sub, "", depth + 1))
        return "\n".join(filter(None, lines))
        