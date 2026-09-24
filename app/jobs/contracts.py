"""Versioned job and planner contracts. Model output proposes work; it cannot authorize tools."""

import hashlib
import json
from typing import Literal
from uuid import UUID

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings
from app.errors import NexusError

JobMode = Literal["answer", "comparison", "synthesis", "evidence", "agentic"]
TERMINAL_JOBS = {"completed", "completed_with_gaps", "failed", "cancelled"}
TERMINAL_TASKS = {"succeeded", "failed", "cancelled", "skipped"}
PLAN_VERSION = "plan.v1"


class SourcePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allow_web: bool = False
    allowed_domains: list[str] = Field(default_factory=list, max_length=5)
    web_urls: list[str] = Field(default_factory=list, max_length=5)


class BudgetOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_tasks: int | None = Field(default=None, ge=4)
    max_depth: int | None = Field(default=None, ge=3)
    max_parallel_tasks: int | None = Field(default=None, ge=1)
    max_provider_calls: int | None = Field(default=None, ge=1)
    max_input_tokens: int | None = Field(default=None, ge=1)
    max_output_tokens: int | None = Field(default=None, ge=1)
    max_duration_seconds: int | None = Field(default=None, ge=10)


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    workspace_id: UUID
    question: str = Field(min_length=1, max_length=4000)
    source_ids: list[UUID] = Field(default_factory=list, max_length=10)
    mode: JobMode = "agentic"
    top_k_per_source: int = Field(default=4, ge=1, le=20)
    policy: SourcePolicy = Field(default_factory=SourcePolicy)
    budget: BudgetOptions = Field(default_factory=BudgetOptions)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str | None = Field(default=None, max_length=4000)
    source_ids: list[str] = Field(default_factory=list, max_length=10)
    url_index: int | None = Field(default=None, ge=0, le=4)


class PlannedTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_-]*$")
    type: Literal[
        "fetch_web", "retrieve_internal", "extract_evidence", "synthesize", "validate_result"
    ]
    depends_on: list[str] = Field(default_factory=list, max_length=12)
    input: TaskInput = Field(default_factory=TaskInput)
    optional: bool = False


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["plan.v1"] = PLAN_VERSION
    tasks: list[PlannedTask] = Field(min_length=3, max_length=30)


def canonical_hash(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def budget_limits(options: BudgetOptions, settings: Settings) -> dict:
    limits = {
        "max_tasks": settings.max_job_tasks,
        "max_depth": settings.max_job_depth,
        "max_parallel_tasks": settings.max_job_parallel_tasks,
        "max_provider_calls": settings.max_job_provider_calls,
        "max_input_tokens": settings.max_job_input_tokens,
        "max_output_tokens": settings.max_job_output_tokens,
        "max_duration_seconds": settings.job_timeout_seconds,
    }
    for name, value in options.model_dump(exclude_none=True).items():
        if value > limits[name]:
            raise NexusError("BUDGET_EXCEEDED", f"{name} exceeds the local configured limit.")
        limits[name] = value
    return limits


def fixed_plan(question: str, mode: str, web_urls: list[str]) -> Plan:
    """Simple modes have a known workflow and do not need a paid planning call."""
    tasks = [
        PlannedTask(
            key=f"web_{index}", type="fetch_web", optional=True, input=TaskInput(url_index=index)
        )
        for index in range(len(web_urls))
    ]
    tasks.append(
        PlannedTask(
            key="retrieve",
            type="retrieve_internal",
            depends_on=[task.key for task in tasks],
            input=TaskInput(question=question),
        )
    )
    tasks.append(PlannedTask(key="evidence", type="extract_evidence", depends_on=["retrieve"]))
    if mode != "evidence":
        tasks.append(PlannedTask(key="synthesis", type="synthesize", depends_on=["evidence"]))
    tasks.append(
        PlannedTask(
            key="validate",
            type="validate_result",
            depends_on=["evidence" if mode == "evidence" else "synthesis"],
        )
    )
    return Plan(tasks=tasks)


def validate_plan(
    plan: Plan, *, source_ids: set[str], web_urls: list[str], limits: dict, mode: str
) -> None:
    """NetworkX handles graph algorithms; these checks enforce our research contract."""

    def reject(message: str) -> None:
        raise NexusError("PLAN_REJECTED", message, 422)

    keys = [task.key for task in plan.tasks]
    if len(keys) != len(set(keys)) or len(keys) > limits["max_tasks"]:
        reject("Task keys must be unique and within the task budget.")
    graph = nx.DiGraph()
    graph.add_nodes_from(keys)
    by_type: dict[str, list[PlannedTask]] = {}
    for task in plan.tasks:
        by_type.setdefault(task.type, []).append(task)
        if len(task.depends_on) != len(set(task.depends_on)):
            reject("Task dependencies must be distinct.")
        if any(key not in keys for key in task.depends_on):
            reject("Every dependency must name a task in this plan.")
        graph.add_edges_from((parent, task.key) for parent in task.depends_on)
        if task.optional and task.type != "fetch_web":
            reject("Only explicitly approved web acquisitions may be optional.")
        if task.type == "retrieve_internal":
            if not task.input.question or not task.input.question.strip():
                reject("Retrieval requires a bounded research question.")
            selected = set(task.input.source_ids)
            if selected and selected != source_ids:
                reject("Retrieval cannot expand or silently narrow the approved source set.")
            if task.input.url_index is not None:
                reject("Retrieval cannot choose a URL.")
        elif task.type == "fetch_web":
            if task.input.url_index not in range(len(web_urls)) or not task.optional:
                reject("Web tasks must refer to an approved URL index and allow explicit gaps.")
            if task.depends_on or task.input.source_ids or task.input.question is not None:
                reject("Web acquisition has no model-selected sources or query.")
        elif task.input != TaskInput():
            reject("Evidence, synthesis, and validation consume persisted dependency outputs.")
    if not nx.is_directed_acyclic_graph(graph):
        reject("The research plan contains a cycle.")
    if nx.dag_longest_path_length(graph) + 1 > limits["max_depth"]:
        reject("The plan exceeds the graph-depth budget.")
    if max(dict(graph.out_degree()).values()) > 6:
        reject("The plan exceeds the six-branch fan-out limit.")
    for kind in ("extract_evidence", "validate_result"):
        if len(by_type.get(kind, [])) != 1:
            reject(f"The plan needs exactly one {kind} task.")
    retrieval = by_type.get("retrieve_internal", [])
    if not 1 <= len(retrieval) <= 3:
        reject("A plan requires one to three retrieval questions.")
    fetches = by_type.get("fetch_web", [])
    if sorted(task.input.url_index for task in fetches) != list(range(len(web_urls))):
        reject("Every approved URL must have exactly one acquisition task.")
    for task in retrieval:
        if not {fetch.key for fetch in fetches}.issubset(nx.ancestors(graph, task.key)):
            reject("Retrieval must wait until approved web acquisitions have settled.")
        if any(
            next(item for item in plan.tasks if item.key == parent).type != "fetch_web"
            for parent in task.depends_on
        ):
            reject("Retrieval may depend only on approved acquisitions.")
    evidence = by_type["extract_evidence"][0]
    if set(evidence.depends_on) != {task.key for task in retrieval}:
        reject("Evidence must join all retrieval branches.")
    terminal = by_type["validate_result"][0]
    syntheses = by_type.get("synthesize", [])
    if mode == "evidence":
        if syntheses or terminal.depends_on != [evidence.key]:
            reject("Evidence-only runs must not call a synthesis provider.")
    elif len(syntheses) != 1 or syntheses[0].depends_on != [evidence.key]:
        reject("Exactly one synthesis must consume validated evidence.")
    elif terminal.depends_on != [syntheses[0].key]:
        reject("Final validation must follow synthesis.")
    if set(nx.ancestors(graph, terminal.key)) != set(keys) - {terminal.key}:
        reject("Every task must contribute to the final validation path.")
    minimum_calls = len(retrieval) + len(fetches) + (mode != "evidence") + (mode == "agentic")
    if minimum_calls > limits["max_provider_calls"]:
        reject("The plan cannot fit the provider-call budget.")
