from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)


class ConceptBlock(StrictContract):
    label: str = Field(min_length=1, max_length=120)
    terms: list[str] = Field(min_length=1, max_length=20)
    exclude_terms: list[str] = Field(default_factory=list, max_length=20)


class GapDraft(StrictContract):
    gap_type: Literal["theory", "context", "data", "method", "time", "practice"]
    statement: str = Field(min_length=5, max_length=500)
    why_only_candidate: str = Field(min_length=5, max_length=500)
    counter_search: str = Field(min_length=3, max_length=500)


class ProblemDraft(StrictContract):
    initial_idea: str = Field(min_length=3, max_length=4000)
    research_object: str = Field(min_length=1, max_length=500)
    problem_boundary: str = Field(min_length=3, max_length=1000)
    objective: Literal["explore", "explain", "causal", "predict", "optimize", "synthesize", "theory_build", "unknown"]
    units: list[str] = Field(default_factory=list, max_length=10)
    geography: list[str] = Field(default_factory=list, max_length=10)
    time_window: str = Field(default="", max_length=200)
    concepts: list[ConceptBlock] = Field(min_length=1, max_length=12)
    questions: list[str] = Field(min_length=1, max_length=5)
    candidate_gaps: list[GapDraft] = Field(default_factory=list, max_length=6)
    counter_searches: list[str] = Field(default_factory=list, max_length=10)
    unknowns: list[str] = Field(default_factory=list, max_length=20)


class QueryBlock(StrictContract):
    label: str = Field(min_length=1, max_length=120)
    terms: list[str] = Field(min_length=1, max_length=30)
    exclude_terms: list[str] = Field(default_factory=list, max_length=20)
    query_zh: str = Field(min_length=3, max_length=1000)
    query_en: str = Field(min_length=3, max_length=1000)
    purpose: str = Field(min_length=3, max_length=500)


class LiteraturePlanDraft(StrictContract):
    topic_summary: str = Field(min_length=5, max_length=1000)
    query_blocks: list[QueryBlock] = Field(min_length=2, max_length=12)
    databases: list[Literal["openalex", "crossref", "semantic_scholar", "arxiv"]] = Field(min_length=2, max_length=4)
    languages: list[str] = Field(min_length=1, max_length=8)
    year_from: int | None = Field(default=None, ge=1800, le=2100)
    year_to: int | None = Field(default=None, ge=1800, le=2100)
    inclusion_criteria: list[str] = Field(min_length=1, max_length=20)
    exclusion_criteria: list[str] = Field(min_length=1, max_length=20)
    screening_questions: list[str] = Field(min_length=1, max_length=15)
    counter_searches: list[str] = Field(min_length=1, max_length=12)
    unknowns: list[str] = Field(default_factory=list, max_length=20)
    coverage_limits: list[str] = Field(min_length=1, max_length=15)


class ResearchStreamDraft(StrictContract):
    stream_id: str = Field(pattern=r"^stream_[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=5, max_length=800)
    paper_ids: list[str] = Field(min_length=1, max_length=30)
    naming_evidence: str = Field(min_length=5, max_length=500)


class SynthesisStatementDraft(StrictContract):
    statement: str = Field(min_length=5, max_length=800)
    status: Literal["supported", "contested", "limited", "not_found", "inference"]
    supporting_paper_ids: list[str] = Field(default_factory=list, max_length=30)
    opposing_paper_ids: list[str] = Field(default_factory=list, max_length=30)
    qualifiers: list[str] = Field(default_factory=list, max_length=12)


class EvidenceGapDraft(StrictContract):
    gap_type: Literal["theory", "context", "data", "method", "time", "practice"]
    statement: str = Field(min_length=5, max_length=600)
    supporting_paper_ids: list[str] = Field(default_factory=list, max_length=20)
    opposing_paper_ids: list[str] = Field(default_factory=list, max_length=20)
    counter_search: str = Field(min_length=3, max_length=500)
    coverage_limitations: list[str] = Field(min_length=1, max_length=10)


class LiteratureSynthesisDraft(StrictContract):
    research_streams: list[ResearchStreamDraft] = Field(min_length=1, max_length=8)
    syntheses: list[SynthesisStatementDraft] = Field(min_length=1, max_length=15)
    gap_candidates: list[EvidenceGapDraft] = Field(default_factory=list, max_length=8)
    recommended_next_steps: list[str] = Field(min_length=1, max_length=12)
    unknowns: list[str] = Field(default_factory=list, max_length=20)
    coverage_limits: list[str] = Field(min_length=1, max_length=15)


class TheoreticalLensDraft(StrictContract):
    name: str = Field(min_length=2, max_length=160)
    relevance: str = Field(min_length=5, max_length=600)
    limits: list[str] = Field(min_length=1, max_length=8)
    supporting_paper_ids: list[str] = Field(default_factory=list, max_length=20)


class ConstructDraft(StrictContract):
    name: str = Field(min_length=1, max_length=120)
    definition: str = Field(min_length=5, max_length=500)
    role: Literal["antecedent", "outcome", "mediator", "moderator", "control", "context", "parameter"]
    measurement_unknowns: list[str] = Field(default_factory=list, max_length=8)


class MechanismDraft(StrictContract):
    name: str = Field(min_length=2, max_length=120)
    chain: list[str] = Field(min_length=2, max_length=8)
    boundary_conditions: list[str] = Field(default_factory=list, max_length=10)
    supporting_paper_ids: list[str] = Field(default_factory=list, max_length=20)
    evidence_status: Literal["supported", "contested", "limited", "inference", "needs_evidence"]


class CompetingExplanationDraft(StrictContract):
    explanation: str = Field(min_length=5, max_length=600)
    distinguishing_observation: str = Field(min_length=5, max_length=600)


class PropositionDraft(StrictContract):
    proposition_id: str = Field(pattern=r"^(RQ|H|P)[0-9_-]+$")
    statement: str = Field(min_length=5, max_length=600)
    falsification: str = Field(min_length=5, max_length=600)


class TheoryDraft(StrictContract):
    theoretical_lenses: list[TheoreticalLensDraft] = Field(min_length=1, max_length=6)
    constructs: list[ConstructDraft] = Field(min_length=2, max_length=20)
    mechanisms: list[MechanismDraft] = Field(min_length=1, max_length=10)
    research_questions: list[str] = Field(min_length=1, max_length=5)
    competing_explanations: list[CompetingExplanationDraft] = Field(min_length=1, max_length=8)
    falsifiable_propositions: list[PropositionDraft] = Field(min_length=1, max_length=10)
    contribution_boundary: str = Field(min_length=5, max_length=1000)
    unknowns: list[str] = Field(default_factory=list, max_length=20)


class MethodOptionDraft(StrictContract):
    method_id: str = Field(pattern=r"^M[0-9]{2}$")
    role: Literal["primary", "alternative", "supporting"]
    rationale: str = Field(min_length=5, max_length=600)
    fit_conditions: list[str] = Field(min_length=1, max_length=10)
    risks: list[str] = Field(min_length=1, max_length=10)


class AssumptionDraft(StrictContract):
    assumption_id: str = Field(min_length=2, max_length=80)
    category: Literal["identification", "measurement", "behavioral", "mathematical", "data", "deployment"]
    statement: str = Field(min_length=5, max_length=600)
    testability: Literal["testable", "partially_testable", "untestable"]
    planned_check: str = Field(min_length=3, max_length=500)


class DesignDraft(StrictContract):
    design_lane: Literal["empirical_causal", "analytical_optimization", "predictive_computational", "behavioral_qualitative", "synthesis_design_science"]
    research_question: str = Field(min_length=5, max_length=800)
    unit_of_analysis: str = Field(min_length=1, max_length=300)
    estimand_or_objective: str = Field(min_length=5, max_length=800)
    method_options: list[MethodOptionDraft] = Field(min_length=2, max_length=8)
    primary_method_id: str = Field(pattern=r"^M[0-9]{2}$")
    assumptions: list[AssumptionDraft] = Field(min_length=1, max_length=20)
    falsification: list[str] = Field(min_length=1, max_length=12)
    threats_to_validity: list[str] = Field(min_length=1, max_length=15)
    stopping_conditions: list[str] = Field(min_length=1, max_length=10)
    unknowns: list[str] = Field(default_factory=list, max_length=20)


class DataSourceChoiceDraft(StrictContract):
    source_id: str = Field(pattern=r"^D[0-9]{2}$")
    role: Literal["primary", "supplementary", "validation", "candidate"]
    access_status: Literal["unknown", "available", "requested", "blocked"]
    license_status: Literal["unknown", "cleared", "restricted", "pending", "not_applicable"]
    rationale: str = Field(min_length=5, max_length=600)
    required_fields: list[str] = Field(default_factory=list, max_length=30)
    risks: list[str] = Field(min_length=1, max_length=12)


class VariableDraft(StrictContract):
    name: str = Field(min_length=1, max_length=160)
    role: Literal["outcome", "treatment", "exposure", "predictor", "control", "mediator", "moderator", "parameter", "index"]
    construct_name: str = Field(alias="construct", min_length=1, max_length=200)
    operationalization: str = Field(min_length=3, max_length=800)
    unit: str = Field(min_length=1, max_length=160)
    source_ids: list[str] = Field(default_factory=list, max_length=10)
    missing_data_plan: str = Field(min_length=3, max_length=500)


class DataDraft(StrictContract):
    data_sources: list[DataSourceChoiceDraft] = Field(min_length=1, max_length=10)
    variables: list[VariableDraft] = Field(min_length=2, max_length=30)
    sample_definition: str = Field(min_length=5, max_length=800)
    time_coverage: str = Field(min_length=1, max_length=300)
    join_keys: list[str] = Field(default_factory=list, max_length=15)
    pii_class: Literal["none", "low", "sensitive", "restricted", "unknown"]
    privacy_risks: list[str] = Field(default_factory=list, max_length=15)
    ethics_checks: list[str] = Field(min_length=1, max_length=15)
    quality_checks: list[str] = Field(min_length=1, max_length=20)
    blocking_issues: list[str] = Field(default_factory=list, max_length=15)
    unknowns: list[str] = Field(default_factory=list, max_length=20)
