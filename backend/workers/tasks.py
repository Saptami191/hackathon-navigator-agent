import time
import uuid
from celery import Celery
from celery.utils.log import get_task_logger

from core.config import settings

logger = get_task_logger(__name__)

celery_app = Celery(
    "hackathon_navigator_eval",
    broker=str(settings.redis_url).replace("/0", f"/{settings.redis_celery_db}"),
    backend=str(settings.redis_url).replace("/0", f"/{settings.redis_celery_db}"),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="workers.tasks.run_evaluation_suite_task")
def run_evaluation_suite_task(suite_id: str, agent_version_id: str, evaluation_run_id: str, trigger: str = "manual"):
    """Run an evaluation suite by executing each benchmark case against the specified agent version."""
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from db.models import EvaluationRun, BenchmarkCase
    from app.services.evaluation_service import EvaluationService
    from app.repositories.evaluation_repository import EvaluationRepository
    from app.repositories.agent_repository import AgentRepository
    from importlib import import_module

    engine = create_async_engine(str(settings.database_url))
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async def _run():
        async with async_session() as session:
            eval_repo = EvaluationRepository(session)
            run = await eval_repo.get_run(evaluation_run_id)
            if not run:
                return

            # update run status
            run.status = "running"
            run.started_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
            await session.commit()

            # load agent callable
            agent_repo = AgentRepository(session)
            agent = await agent_repo.get_version(agent_version_id)
            if not agent:
                run.status = "failed"
                run.error_message = f"Agent version {agent_version_id} not found"
                await session.commit()
                return

            module_name, func_name = agent.callable_path.rsplit('.', 1)
            module = import_module(module_name)
            agent_callable = getattr(module, func_name)

            # gather cases
            result = await session.execute(__import__('sqlalchemy').select(BenchmarkCase).where(BenchmarkCase.suite_id == suite_id, BenchmarkCase.is_active == True))
            cases = result.scalars().all()

            total = len(cases)
            completed = 0
            acc_sum = 0.0
            latencies = []
            tokens = 0
            costs = 0.0
            case_executions = []

            evaluation_service = EvaluationService(session)

            for case in cases:
                try:
                    case_exec = await evaluation_service.create_case_execution(str(run.id), case)
                    output, metrics, traces = await evaluation_service.execute_benchmark_case(agent_callable, case)

                    case_exec.output_payload = output
                    case_exec.metrics = metrics
                    case_exec.latency_seconds = metrics.get('latency_seconds')
                    case_exec.tokens_used = metrics.get('tokens_used')
                    case_exec.cost_usd = metrics.get('cost_usd')
                    case_exec.status = "completed"
                    case_exec.completed_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
                    await session.commit()

                    completed += 1
                    acc_sum += metrics.get('accuracy', 0.0)
                    latencies.append(metrics.get('latency_seconds', 0.0))
                    tokens += metrics.get('tokens_used', 0)
                    costs += metrics.get('cost_usd', 0.0)
                    case_executions.append(case_exec)

                    # store traces
                    for t in traces:
                        await eval_repo.create_trace(
                            case_execution_id=str(case_exec.id),
                            step_name=t.get('step_name', 'step'),
                            prompt=t.get('prompt'),
                            retrieved_context=t.get('retrieved_context'),
                            tool_calls=t.get('tool_calls'),
                            intermediate_reasoning=t.get('intermediate_reasoning'),
                            model_response=t.get('model_response'),
                            output=t.get('output'),
                        )

                except Exception as e:
                    # record failure
                    await eval_repo.create_regression_alert(
                        evaluation_run_id=str(run.id),
                        agent_version_id=str(agent.id),
                        benchmark_case_id=str(case.id),
                        alert_type='case_execution_failure',
                        severity='high',
                        message=str(e),
                        indicators={'exception': str(e)},
                    )

            # finalize run
            run.status = "completed"
            run.completed_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
            run.total_cases = total
            run.completed_cases = completed
            run.accuracy = (acc_sum / completed) if completed else 0.0
            run.average_latency_ms = (sum(latencies) / len(latencies) * 1000) if latencies else 0.0
            run.token_usage_total = tokens
            run.average_cost_usd = (costs / completed) if completed else 0.0
            run.completion_rate = (completed / total) if total else 0.0
            run.tool_success_rate = 1.0 - (len([c for c in case_executions if c.status != 'completed']) / total) if total else 1.0
            await session.commit()

            # generate regression alerts comparing to previous run of same suite/agent
            prev = await session.execute(__import__('sqlalchemy').select(EvaluationRun).where(EvaluationRun.suite_id == suite_id, EvaluationRun.agent_version_id == agent_version_id).order_by(EvaluationRun.created_at.desc()).limit(1))
            previous_run = prev.scalar_one_or_none()
            await evaluation_service.generate_regression_alerts(run, previous_run, case_executions)

        await engine.dispose()

    asyncio.run(_run())
