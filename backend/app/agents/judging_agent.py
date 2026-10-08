"""
Judging Intelligence Agent.

Evaluates a hackathon project against judging criteria and identifies
the highest-impact improvements.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from structlog import get_logger

from core.config import settings

logger = get_logger(__name__)


def get_judging_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model=settings.claude_model,
        api_key=settings.anthropic_api_key,
        max_tokens=4096,
        temperature=0.1,
    )


def extract_json(content: str) -> dict[str, Any]:
    """Extract JSON object from LLM response."""
    match = re.search(r"\{.*\}", content, re.DOTALL)

    if not match:
        raise ValueError("Judging agent returned invalid JSON")

    return json.loads(match.group())


async def judging_agent_node(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Evaluate the project from a hackathon judge's perspective.
    """

    logger.info(
        "JudgingAgent starting",
        project_id=state["project_id"],
    )

    criteria = state.get("judging_criteria") or [
        "Technical Implementation",
        "Innovation",
        "Impact",
        "Demo Quality",
    ]

    repo = state.get("repo_analysis") or {}

    prompt = f"""
You are an expert hackathon judge and senior technical evaluator.

Evaluate this project strictly from a judge's perspective.

PROJECT
-------
Name: {state.get("project_name")}

Hackathon Theme:
{state.get("hackathon_theme") or "Not specified"}

Project Goals:
{json.dumps(state.get("project_goals", []))}

Judging Criteria:
{json.dumps(criteria)}

ARCHITECTURE
------------
{state.get("architecture_summary") or "Not available"}

TECH STACK
----------
{json.dumps(state.get("tech_stack", []))}

REPOSITORY EVIDENCE
-------------------
{json.dumps(repo, indent=2)[:7000]}

EXISTING TASKS
--------------
{json.dumps(state.get("tasks", []), indent=2)[:4000]}

Return ONLY valid JSON.

Use this exact structure:

{{
    "overall_score": 0,

    "criteria": [
        {{
            "name": "Technical Implementation",
            "score": 0,
            "weight": 25,

            "evidence": [
                "specific evidence from repository"
            ],

            "gaps": [
                "specific weakness"
            ],

            "actions": [
                {{
                    "title": "specific improvement",
                    "description": "what should be built",
                    "estimated_hours": 2,
                    "expected_score_gain": 5
                }}
            ]
        }}
    ],

    "top_actions": [
        {{
            "title": "highest impact action",
            "description": "what to build",
            "estimated_hours": 2,
            "expected_score_gain": 5,
            "reason": "why judges would care"
        }}
    ],

    "critical_gaps": [
        "important missing capability"
    ]
}}

RULES:

1. Score every criterion from 0-10.

2. Weights must sum to 100.

3. Do NOT invent features that are not supported by
   the repository evidence.

4. Be harsh and realistic.

5. Prefer measurable improvements over UI polish.

6. Prioritize actions based on:

       expected score gain / implementation effort

7. Focus on what can actually improve the hackathon result.

8. Evidence must come from the supplied repository/project information.

9. "overall_score" must be between 0 and 100.
"""

    try:
        llm = get_judging_llm()

        response = await llm.ainvoke(
            [HumanMessage(content=prompt)]
        )

        result = extract_json(response.content)

        # Calculate weighted score ourselves instead of
        # trusting the LLM's arithmetic.
        criteria_results = result.get("criteria", [])

        weighted_score = 0.0
        total_weight = 0.0

        for criterion in criteria_results:
            score = float(criterion.get("score", 0))
            weight = float(criterion.get("weight", 0))

            weighted_score += score * weight
            total_weight += weight

        if total_weight > 0:
            result["overall_score"] = round(
                (weighted_score / total_weight) * 10,
                1,
            )

        result["overall_score"] = max(
            0,
            min(100, float(result.get("overall_score", 0))),
        )

        # Add top actions to recommendations.
        recommendations = list(
            state.get("recommendations", [])
        )

        for action in result.get("top_actions", []):
            title = action.get("title")

            if title and title not in recommendations:
                recommendations.append(title)

        return {
            "judging_assessment": result,
            "recommendations": recommendations,
            "agents_completed": (
                state.get("agents_completed", [])
                + ["judging_agent"]
            ),
            "current_agent": "tech_reviewer",
            "messages": [],
        }

    except Exception as exc:
        logger.error(
            "JudgingAgent failed",
            error=str(exc),
        )

        return {
            "judging_assessment": {
                "overall_score": 0,
                "criteria": [],
                "top_actions": [],
                "critical_gaps": [
                    f"Judging evaluation failed: {exc}"
                ],
            },
            "agents_completed": (
                state.get("agents_completed", [])
                + ["judging_agent"]
            ),
            "current_agent": "tech_reviewer",
        }
        