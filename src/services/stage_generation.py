from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Callable

from inference.gateway import InferenceGateway, InferenceResponse, OpenAICompatibleGateway
from inference.structured import StructuredOutputError, validate_structured_output
from knowledge import KnowledgeRegistry
from prompts.catalog import PromptCatalog


class StageGenerationNotSupportedError(LookupError):
    pass


class StageGenerationOutputError(RuntimeError):
    pass


class StageGenerationService:
    def __init__(
        self,
        gateway_factory: Callable[[], InferenceGateway] | None = None,
    ) -> None:
        self.gateway_factory = gateway_factory or OpenAICompatibleGateway

    async def generate(
        self,
        project: dict[str, Any],
        stage_key: str,
        instruction: str = "",
    ) -> dict[str, Any]:
        context = self._build_context(project, stage_key)
        prompt = PromptCatalog.get(stage_key, context)
        if prompt is None:
            raise StageGenerationNotSupportedError(
                f"model generation is not implemented for stage '{stage_key}'"
            )

        system_prompt, user_prompt = prompt.render(context, instruction)
        gateway = self.gateway_factory()
        responses: list[InferenceResponse] = []

        first = await gateway.generate(system_prompt, user_prompt)
        responses.append(first)
        try:
            draft = validate_structured_output(first.text, prompt.contract)
            self._validate_domain_references(draft.model_dump(mode="json"), prompt.prompt_id, context)
        except StructuredOutputError as first_error:
            repair_prompt = f"""上一次输出未通过结构或引用约束：{first_error}

请只修复 JSON 格式、字段和值，使其符合原任务、JSON Schema 和输入中的可用 ID。
不得增加输入中不存在的事实、论文、方法或数据源。

原任务与约束：
{user_prompt[:12000]}

待修复输出：
{first.text[:12000]}"""
            repaired = await gateway.generate(system_prompt, repair_prompt)
            responses.append(repaired)
            try:
                draft = validate_structured_output(repaired.text, prompt.contract)
                self._validate_domain_references(draft.model_dump(mode="json"), prompt.prompt_id, context)
            except StructuredOutputError as final_error:
                raise StageGenerationOutputError(str(final_error)) from final_error

        content = draft.model_dump(mode="json")
        if stage_key == "problem":
            content["initial_idea"] = project["initial_idea"]
        content["generation"] = {
            "mode": "model",
            "prompt_id": prompt.prompt_id,
            "prompt_version": prompt.version,
            "model": responses[-1].model,
            "generated_at": datetime.now(UTC).isoformat(),
            "attempts": len(responses),
            "usage": self._merge_usage(responses),
        }
        return content

    @staticmethod
    def _build_context(project: dict[str, Any], stage_key: str) -> dict[str, Any]:
        stages = {stage["key"]: stage for stage in project.get("stages", [])}
        context: dict[str, Any] = {
            "project_id": project["project_id"],
            "title": project["title"],
            "initial_idea": project["initial_idea"],
            "stage": stage_key,
            "current_stage_content": stages.get(stage_key, {}).get("content", {}),
        }
        if stage_key == "literature":
            problem = stages.get("problem", {})
            context["problem_revision"] = problem.get("revision", 0)
            context["problem_content"] = problem.get("content", {})
            current = stages.get("literature", {}).get("content", {})
            if current.get("papers"):
                context["current_stage_content"] = {
                    "topic_summary": current.get("topic_summary", ""),
                    "query_blocks": current.get("query_blocks", []),
                    "inclusion_criteria": current.get("inclusion_criteria", []),
                    "exclusion_criteria": current.get("exclusion_criteria", []),
                    "screening_questions": current.get("screening_questions", []),
                    **StageGenerationService._compact_literature(current),
                }
        if stage_key in {"theory", "design", "data"}:
            problem = stages.get("problem", {})
            literature = stages.get("literature", {})
            context["problem_content"] = problem.get("content", {})
            context["literature_content"] = StageGenerationService._compact_literature(
                literature.get("content", {})
            )
        if stage_key in {"design", "data"}:
            context["theory_content"] = stages.get("theory", {}).get("content", {})
        if stage_key == "design":
            goal = str(context.get("problem_content", {}).get("objective", ""))
            query = f"{project['title']} {json_text(context.get('theory_content', {}))}"
            context["method_candidates"] = KnowledgeRegistry.method_candidates(goal, query, 10)
        if stage_key == "data":
            design_content = stages.get("design", {}).get("content", {})
            context["design_content"] = design_content
            query = f"{project['title']} {json_text(design_content)}"
            context["data_source_candidates"] = KnowledgeRegistry.data_source_candidates(query, 12)
        return context

    @staticmethod
    def _compact_literature(content: dict[str, Any]) -> dict[str, Any]:
        papers = []
        for item in content.get("papers", [])[:30]:
            if not isinstance(item, dict):
                continue
            papers.append(
                {
                    "paper_id": item.get("paper_id", ""),
                    "title": item.get("title", ""),
                    "authors": item.get("authors", [])[:5],
                    "year": item.get("year", ""),
                    "doi": item.get("doi", ""),
                    "abstract": str(item.get("abstract", ""))[:800],
                }
            )
        return {
            "papers": papers,
            "research_streams": content.get("research_streams", []),
            "syntheses": content.get("syntheses", []),
            "gap_candidates": content.get("gap_candidates", []),
            "coverage_limits": content.get("coverage_limits", []),
        }

    @staticmethod
    def _validate_domain_references(
        content: dict[str, Any],
        prompt_id: str,
        context: dict[str, Any],
    ) -> None:
        if prompt_id in {"ai4ms.stage.literature-synthesis", "ai4ms.stage.theory"}:
            allowed = {
                str(item.get("paper_id"))
                for item in context.get("literature_content", context.get("current_stage_content", {})).get("papers", [])
                if isinstance(item, dict) and item.get("paper_id")
            }
            referenced = set(StageGenerationService._collect_values(content, "paper_ids"))
            invalid = sorted(referenced - allowed)
            if invalid:
                raise StructuredOutputError(f"output references unknown paper_ids: {invalid[:8]}")
        if prompt_id == "ai4ms.stage.design":
            allowed = {str(item.get("method_id")) for item in context.get("method_candidates", [])}
            referenced = set(StageGenerationService._collect_values(content, "method_id"))
            referenced.add(str(content.get("primary_method_id", "")))
            invalid = sorted(item for item in referenced - allowed if item)
            if invalid:
                raise StructuredOutputError(f"output references methods outside the registry shortlist: {invalid[:8]}")
        if prompt_id == "ai4ms.stage.data":
            allowed = {str(item.get("source_id")) for item in context.get("data_source_candidates", [])}
            referenced = set(StageGenerationService._collect_values(content, "source_id"))
            referenced.update(StageGenerationService._collect_values(content, "source_ids"))
            invalid = sorted(item for item in referenced - allowed if item)
            if invalid:
                raise StructuredOutputError(f"output references data sources outside the registry shortlist: {invalid[:8]}")

    @staticmethod
    def _collect_values(value: Any, key_suffix: str) -> list[str]:
        found: list[str] = []
        if isinstance(value, dict):
            for key, item in value.items():
                if key == key_suffix or key.endswith(f"_{key_suffix}"):
                    if isinstance(item, list):
                        found.extend(str(entry) for entry in item)
                    elif item:
                        found.append(str(item))
                else:
                    found.extend(StageGenerationService._collect_values(item, key_suffix))
        elif isinstance(value, list):
            for item in value:
                found.extend(StageGenerationService._collect_values(item, key_suffix))
        return found

    @staticmethod
    def _merge_usage(responses: list[InferenceResponse]) -> dict[str, int]:
        keys = ("input_tokens", "output_tokens", "total_tokens", "call_count")
        return {
            key: sum(int(response.usage.get(key, 0) or 0) for response in responses)
            for key in keys
        }


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)[:12000]
