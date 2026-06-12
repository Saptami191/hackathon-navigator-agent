"""
Supervisor agent built with LangGraph.
Coordinates: RepoAnalyst → Planner → TechReviewer → PitchGenerator → DeadlineManager
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, TypedDict

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from core.config import settings
from services.github_service import GitHubService, RepoAnalysis
from services.rag_service import RAGService

logger = structlog.get_logger(__name__)

# ─── State ────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    project_id: str
    project_name: str
    github_repo_url: str | None
    hackathon_theme: str | None
    submission_deadline: str | None  # ISO format
    judging_criteria: list[str]
    project_goals: list[str]

    # Populated by agents
    repo_analysis: dict[str, Any] | None
    architecture_summary: str | None
    tech_stack: list[str]
    tasks: list[dict[str, Any]]
    blockers: list[dict[str, Any]]
    risk_level: str
    estimated_hours_remaining: float | None
    completion_percentage: float | None
    pitch_content: dict[str, str]
    recommendations: list[str]

    # Control flow
    current_agent: str
    agents_completed: list[str]
    error: str | None
    final_report: dict[str, Any] | None


# ─── LLM ─────────────────────────────────────────────────────────────────────

def get_claude() -> ChatAnthropic:
    return ChatAnthropic(
        model=settings.claude_model,
        api_key=settings.anthropic_api_key,
        max_tokens=4096,
        temperature=0.2,
    )


# ─── Agent nodes ─────────────────────────────────────────────────────────────

async def repo_analyst_node(state: AgentState) -> dict[str, Any]:
    """Analyzes the GitHub repository and populates repo_analysis."""
    logger.info("RepoAnalyst starting", project_id=state["project_id"])

    if not state.get("github_repo_url"):
        return {
            "agents_completed": state.get("agents_completed", []) + ["repo_analyst"],
            "current_agent": "planner",
            "messages": [AIMessage(content="No GitHub repo URL provided, skipping repo analysis.")],
        }

    try:
        async with GitHubService() as gh:
            analysis: RepoAnalysis = await gh.analyze_repository(state["github_repo_url"])

        # Serialize for state
        analysis_dict = {
            "name": analysis.name,
            "full_name": analysis.full_name,
            "description": analysis.description,
            "languages": analysis.languages,
            "topics": analysis.topics,
            "readme_preview": (analysis.readme_content or "")[:2000],
            "folder_structure": analysis.folder_structure,
            "open_issues_count": analysis.open_issues_count,
            "open_prs": [
                {"number": pr.number, "title": pr.title, "author": pr.author}
                for pr in analysis.open_prs
            ],
            "open_issues": [
                {
                    "number": i.number,
                    "title": i.title,
                    "is_bug": i.is_bug,
                    "is_feature": i.is_feature,
                    "labels": i.labels,
                }
                for i in analysis.open_issues
            ],
            "recent_commits": [
                {
                    "sha": c.sha,
                    "message": c.message,
                    "author": c.author,
                    "timestamp": c.timestamp.isoformat(),
                }
                for c in analysis.recent_commits[:10]
            ],
            "contributors": analysis.contributors,
            "inactive_contributors": analysis.inactive_contributors,
            "commit_frequency": analysis.commit_frequency,
            "last_commit_at": analysis.last_commit_at.isoformat() if analysis.last_commit_at else None,
        }

        # Ingest into RAG
        rag = RAGService()
        await rag.ingest_repository(state["project_id"], analysis)

        # Generate architecture summary with Claude
        llm = get_claude()
        arch_prompt = f"""Analyze this repository and provide a concise technical architecture summary.

Repository: {analysis.name}
Description: {analysis.description}
Languages: {json.dumps(analysis.languages)}
Structure: {json.dumps(analysis.folder_structure, indent=2)[:3000]}
README excerpt: {(analysis.readme_content or '')[:1500]}

Provide:
1. Architecture pattern (MVC, microservices, monorepo, etc.)
2. Core technologies and frameworks detected
3. Main components and their responsibilities
4. Integration points (APIs, databases, external services)
5. Code quality indicators

Be concise and technical. Max 400 words."""

        arch_response = await llm.ainvoke([HumanMessage(content=arch_prompt)])
        arch_summary = arch_response.content

        tech_stack = list(analysis.languages.keys())

        return {
            "repo_analysis": analysis_dict,
            "architecture_summary": arch_summary,
            "tech_stack": tech_stack,
            "agents_completed": state.get("agents_completed", []) + ["repo_analyst"],
            "current_agent": "planner",
            "messages": [AIMessage(content=f"Repository analysis complete: {analysis.name}")],
        }

    except Exception as e:
        logger.error("RepoAnalyst failed", error=str(e))
        return {
            "error": f"Repository analysis failed: {str(e)}",
            "agents_completed": state.get("agents_completed", []) + ["repo_analyst"],
            "current_agent": "planner",
            "messages": [AIMessage(content=f"Repository analysis failed: {e}")],
        }


async def planner_node(state: AgentState) -> dict[str, Any]:
    """Generates prioritized task list based on repo state and project goals."""
    logger.info("Planner starting", project_id=state["project_id"])

    llm = get_claude()

    # Search RAG for relevant context
    rag = RAGService()
    context_chunks = []
    try:
        chunks = await rag.search(
            state["project_id"],
            "project features implementation tasks missing functionality",
            top_k=6,
        )
        context_chunks = [c["content"] for c in chunks]
    except Exception:
        pass

    deadline_str = state.get("submission_deadline")
    hours_until_deadline = None
    if deadline_str:
        try:
            deadline = datetime.fromisoformat(deadline_str)
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            delta = deadline - datetime.now(timezone.utc)
            hours_until_deadline = max(0, delta.total_seconds() / 3600)
        except Exception:
            pass

    repo_summary = json.dumps(state.get("repo_analysis") or {}, indent=2)[:3000]
    context = "\n\n---\n\n".join(context_chunks[:4])

    prompt = f"""You are a senior hackathon strategist. Generate a precise, prioritized task plan.

PROJECT CONTEXT:
Name: {state["project_name"]}
Theme: {state.get("hackathon_theme", "Not specified")}
Goals: {json.dumps(state.get("project_goals", []))}
Judging criteria: {json.dumps(state.get("judging_criteria", []))}
Hours until deadline: {hours_until_deadline or "Unknown"}

REPOSITORY STATE:
{repo_summary}

CODEBASE CONTEXT:
{context}

Generate a JSON response with this exact structure:
{{
  "tasks": [
    {{
      "title": "string",
      "description": "string",
      "priority": "critical|high|medium|low",
      "category": "feature|bug|tech_debt|missing|demo|docs",
      "estimated_hours": 0.5,
      "is_blocker": false,
      "impact_score": 8.5,
      "rationale": "Why this matters for winning"
    }}
  ],
  "blockers": [
    {{
      "title": "string",
      "description": "string",
      "resolution": "How to fix it"
    }}
  ],
  "completion_percentage": 45.0,
  "scope_reduction_needed": false,
  "scope_reduction_suggestions": []
}}

Prioritize by: (1) demo-ability for judges, (2) core functionality, (3) polish.
Generate 8-15 tasks. Be specific and actionable."""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content

        # Extract JSON
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            plan = json.loads(json_match.group())
        else:
            plan = {"tasks": [], "blockers": [], "completion_percentage": 0}

        return {
            "tasks": plan.get("tasks", []),
            "blockers": plan.get("blockers", []),
            "completion_percentage": plan.get("completion_percentage", 0),
            "agents_completed": state.get("agents_completed", []) + ["planner"],
            "current_agent": "tech_reviewer",
            "messages": [AIMessage(content=f"Generated {len(plan.get('tasks', []))} tasks")],
        }

    except Exception as e:
        logger.error("Planner failed", error=str(e))
        return {
            "error": f"Planning failed: {str(e)}",
            "agents_completed": state.get("agents_completed", []) + ["planner"],
            "current_agent": "tech_reviewer",
        }


async def tech_reviewer_node(state: AgentState) -> dict[str, Any]:
    """Reviews codebase for bugs, performance issues, and architectural improvements."""
    logger.info("TechReviewer starting", project_id=state["project_id"])

    llm = get_claude()
    rag = RAGService()

    # Get code-specific context
    code_chunks = []
    try:
        chunks = await rag.search(
            state["project_id"],
            "code implementation architecture patterns bugs performance",
            top_k=8,
            doc_types=["source_file", "readme"],
        )
        code_chunks = [f"[{c['source']}]\n{c['content']}" for c in chunks]
    except Exception:
        pass

    code_context = "\n\n---\n\n".join(code_chunks[:5])
    arch = state.get("architecture_summary", "Not available")

    prompt = f"""You are a senior staff engineer reviewing a hackathon project.

ARCHITECTURE:
{arch}

CODE SAMPLES:
{code_context[:4000]}

TECH STACK: {json.dumps(state.get("tech_stack", []))}

Provide a technical review as JSON:
{{
  "critical_issues": [
    {{
      "issue": "string",
      "severity": "critical|high|medium",
      "file": "optional filename",
      "fix": "How to fix"
    }}
  ],
  "quick_wins": [
    {{
      "title": "string",
      "description": "Easy improvement with high impact",
      "estimated_minutes": 15
    }}
  ],
  "missing_integrations": ["string"],
  "performance_risks": ["string"],
  "security_concerns": ["string"],
  "recommendations": ["string"]
}}

Focus on what matters for a working hackathon demo. Be direct."""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content

        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        review = json.loads(json_match.group()) if json_match else {}

        # Add tech review tasks to task list
        existing_tasks = list(state.get("tasks", []))
        for issue in review.get("critical_issues", []):
            if issue.get("severity") in ("critical", "high"):
                existing_tasks.insert(0, {
                    "title": f"Fix: {issue['issue']}",
                    "description": issue.get("fix", ""),
                    "priority": "critical" if issue["severity"] == "critical" else "high",
                    "category": "bug",
                    "estimated_hours": 0.5,
                    "is_blocker": issue["severity"] == "critical",
                    "impact_score": 9.0,
                    "rationale": "Critical issue detected by tech reviewer",
                })

        recs = (
            review.get("recommendations", [])
            + review.get("quick_wins_summary", [])
            + [f"Missing integration: {m}" for m in review.get("missing_integrations", [])]
        )

        return {
            "tasks": existing_tasks,
            "recommendations": state.get("recommendations", []) + recs,
            "agents_completed": state.get("agents_completed", []) + ["tech_reviewer"],
            "current_agent": "pitch_generator",
            "messages": [AIMessage(content="Technical review complete")],
        }

    except Exception as e:
        logger.error("TechReviewer failed", error=str(e))
        return {
            "agents_completed": state.get("agents_completed", []) + ["tech_reviewer"],
            "current_agent": "pitch_generator",
        }


async def pitch_generator_node(state: AgentState) -> dict[str, Any]:
    """Generates Devpost submission, elevator pitch, demo script, and architecture explanation."""
    logger.info("PitchGenerator starting", project_id=state["project_id"])

    llm = get_claude()
    rag = RAGService()

    readme_chunks = []
    try:
        chunks = await rag.search(
            state["project_id"],
            "project description features use case impact",
            top_k=5,
            doc_types=["readme", "source_file"],
        )
        readme_chunks = [c["content"] for c in chunks]
    except Exception:
        pass

    context = "\n\n".join(readme_chunks[:3])
    arch = state.get("architecture_summary", "")
    tasks_done = [t for t in state.get("tasks", []) if t.get("category") == "feature"]

    base_prompt = f"""
PROJECT: {state["project_name"]}
THEME: {state.get("hackathon_theme", "General")}
TECH STACK: {json.dumps(state.get("tech_stack", []))}
GOALS: {json.dumps(state.get("project_goals", []))}
JUDGING CRITERIA: {json.dumps(state.get("judging_criteria", []))}
ARCHITECTURE: {arch[:1000]}
CONTEXT: {context[:2000]}
"""

    pitches = {}

    # Devpost submission
    devpost_prompt = base_prompt + """

Write a compelling Devpost submission with these sections:
## Inspiration
## What it does
## How we built it
## Challenges we ran into
## Accomplishments that we're proud of
## What we learned
## What's next for [Project Name]

Be enthusiastic, specific, and technically credible. ~500 words total."""

    devpost_resp = await llm.ainvoke([HumanMessage(content=devpost_prompt)])
    pitches["devpost"] = devpost_resp.content

    # Elevator pitch
    elevator_prompt = base_prompt + """
Write a 60-second elevator pitch (150 words max).
Hook → Problem → Solution → Tech magic → Impact → Call to action.
Make it memorable and exciting for a non-technical judge."""

    elevator_resp = await llm.ainvoke([HumanMessage(content=elevator_prompt)])
    pitches["elevator"] = elevator_resp.content

    # Demo script
    demo_prompt = base_prompt + """
Write a 3-minute demo script with stage directions.
Format:
[SCREEN: What to show]
NARRATOR: What to say
Include: opening hook, core feature demo, wow moment, closing.
Max 400 words."""

    demo_resp = await llm.ainvoke([HumanMessage(content=demo_prompt)])
    pitches["demo_script"] = demo_resp.content

    # Architecture explanation
    arch_prompt = base_prompt + f"""
Write a technical architecture explanation for judges (150 words max).
Explain: system design decisions, why this stack, scalability, key innovations.
Architecture: {arch[:2000]}"""

    arch_resp = await llm.ainvoke([HumanMessage(content=arch_prompt)])
    pitches["architecture"] = arch_resp.content

    return {
        "pitch_content": pitches,
        "agents_completed": state.get("agents_completed", []) + ["pitch_generator"],
        "current_agent": "deadline_manager",
        "messages": [AIMessage(content="Pitch content generated")],
    }


async def deadline_manager_node(state: AgentState) -> dict[str, Any]:
    """Calculates risk level, estimates time-to-completion, recommends scope adjustments."""
    logger.info("DeadlineManager starting", project_id=state["project_id"])

    llm = get_claude()

    deadline_str = state.get("submission_deadline")
    hours_remaining = None
    if deadline_str:
        try:
            deadline = datetime.fromisoformat(deadline_str)
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            delta = deadline - datetime.now(timezone.utc)
            hours_remaining = max(0, delta.total_seconds() / 3600)
        except Exception:
            pass

    tasks = state.get("tasks", [])
    total_estimated = sum(t.get("estimated_hours", 1) for t in tasks if t.get("status") != "completed")
    blockers_count = sum(1 for t in tasks if t.get("is_blocker"))
    completion = state.get("completion_percentage", 0)

    prompt = f"""You are a hackathon deadline strategist.

DEADLINE INTELLIGENCE:
Hours remaining: {hours_remaining or "Unknown"}
Total estimated work hours: {total_estimated:.1f}
Completion percentage: {completion:.0f}%
Blockers: {blockers_count}
Open tasks: {len(tasks)}
Commit frequency (per day): {state.get("repo_analysis", {}).get("commit_frequency", 0):.1f}

Respond with JSON:
{{
  "risk_level": "low|medium|high|critical",
  "risk_factors": ["string"],
  "estimated_hours_to_completion": 12.5,
  "scope_reduction_needed": false,
  "must_have_features": ["string"],
  "cut_features": ["string"],
  "action_items_next_2_hours": ["string"],
  "success_probability": 75,
  "time_recommendation": "string"
}}

Be realistic. A hackathon team can do ~6 effective hours per day."""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        import re
        json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
        assessment = json.loads(json_match.group()) if json_match else {}

        risk_level = assessment.get("risk_level", "medium")

        # Build final report
        final_report = {
            "project_id": state["project_id"],
            "project_name": state["project_name"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "risk_level": risk_level,
            "completion_percentage": completion,
            "estimated_hours_remaining": assessment.get("estimated_hours_to_completion"),
            "success_probability": assessment.get("success_probability"),
            "repo_analysis": state.get("repo_analysis"),
            "architecture_summary": state.get("architecture_summary"),
            "tech_stack": state.get("tech_stack", []),
            "tasks": state.get("tasks", []),
            "blockers": state.get("blockers", []),
            "recommendations": state.get("recommendations", [])
                + assessment.get("action_items_next_2_hours", []),
            "pitch_content": state.get("pitch_content", {}),
            "deadline_assessment": assessment,
            "agents_completed": state.get("agents_completed", []) + ["deadline_manager"],
        }

        return {
            "risk_level": risk_level,
            "estimated_hours_remaining": assessment.get("estimated_hours_to_completion"),
            "final_report": final_report,
            "agents_completed": state.get("agents_completed", []) + ["deadline_manager"],
            "current_agent": "complete",
            "messages": [AIMessage(content=f"Analysis complete. Risk: {risk_level}")],
        }

    except Exception as e:
        logger.error("DeadlineManager failed", error=str(e))
        return {
            "risk_level": "unknown",
            "final_report": {"error": str(e)},
            "agents_completed": state.get("agents_completed", []) + ["deadline_manager"],
            "current_agent": "complete",
        }


# ─── Routing logic ────────────────────────────────────────────────────────────

def route_after_agent(state: AgentState) -> Literal[
    "repo_analyst", "planner", "tech_reviewer", "pitch_generator", "deadline_manager", "__end__"
]:
    current = state.get("current_agent", "complete")
    routing = {
        "repo_analyst": "repo_analyst",
        "planner": "planner",
        "tech_reviewer": "tech_reviewer",
        "pitch_generator": "pitch_generator",
        "deadline_manager": "deadline_manager",
        "complete": "__end__",
    }
    return routing.get(current, "__end__")


# ─── Build graph ──────────────────────────────────────────────────────────────

def build_supervisor_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("repo_analyst", repo_analyst_node)
    graph.add_node("planner", planner_node)
    graph.add_node("tech_reviewer", tech_reviewer_node)
    graph.add_node("pitch_generator", pitch_generator_node)
    graph.add_node("deadline_manager", deadline_manager_node)

    graph.set_entry_point("repo_analyst")

    graph.add_edge("repo_analyst", "planner")
    graph.add_edge("planner", "tech_reviewer")
    graph.add_edge("tech_reviewer", "pitch_generator")
    graph.add_edge("pitch_generator", "deadline_manager")
    graph.add_edge("deadline_manager", END)

    return graph.compile()


supervisor_graph = build_supervisor_graph()


async def run_analysis(
    project_id: str,
    project_name: str,
    github_repo_url: str | None = None,
    hackathon_theme: str | None = None,
    submission_deadline: str | None = None,
    judging_criteria: list[str] | None = None,
    project_goals: list[str] | None = None,
) -> dict[str, Any]:
    """Entry point to run the full multi-agent analysis."""

    initial_state = AgentState(
        messages=[HumanMessage(content=f"Analyze project: {project_name}")],
        project_id=project_id,
        project_name=project_name,
        github_repo_url=github_repo_url,
        hackathon_theme=hackathon_theme,
        submission_deadline=submission_deadline,
        judging_criteria=judging_criteria or [],
        project_goals=project_goals or [],
        repo_analysis=None,
        architecture_summary=None,
        tech_stack=[],
        tasks=[],
        blockers=[],
        risk_level="unknown",
        estimated_hours_remaining=None,
        completion_percentage=None,
        pitch_content={},
        recommendations=[],
        current_agent="repo_analyst",
        agents_completed=[],
        error=None,
        final_report=None,
    )

    result = await supervisor_graph.ainvoke(initial_state)
    return result.get("final_report", {})
    