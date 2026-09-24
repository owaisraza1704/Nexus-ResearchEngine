"""Use the existing Azure SDK adapters with per-job admission and usage accounting."""

import json

import tiktoken
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.job_models import JobBudget, ResearchTask, TaskAttempt
from app.embeddings.azure_openai import embed_texts
from app.errors import NexusError
from app.jobs.state import check_active, event, locked_job
from app.llm.azure_openai import generate_structured


def reserve_call(
    db: Session, job_id, input_tokens: int, output_tokens: int, task: ResearchTask | None
) -> None:
    job = locked_job(db, job_id)
    budget = db.get(JobBudget, job.id, populate_existing=True)
    check_active(job, budget)
    limits = budget.limits
    if (
        budget.used_provider_calls >= limits["max_provider_calls"]
        or budget.used_input_tokens + budget.reserved_input_tokens + input_tokens
        > limits["max_input_tokens"]
        or budget.used_output_tokens + budget.reserved_output_tokens + output_tokens
        > limits["max_output_tokens"]
    ):
        raise NexusError("BUDGET_EXCEEDED", "This provider call would exceed the job budget.", 409)
    budget.used_provider_calls += 1
    budget.reserved_input_tokens += input_tokens
    budget.reserved_output_tokens += output_tokens
    event(
        db,
        job,
        "provider_call_started",
        task=task,
        call_number=budget.used_provider_calls,
        reserved_input_tokens=input_tokens,
        reserved_output_tokens=output_tokens,
    )
    db.commit()


def record_usage(
    db: Session,
    job_id,
    reserved_input: int,
    reserved_output: int,
    actual_input: int | None,
    actual_output: int | None,
    *,
    task: ResearchTask | None,
    attempt: TaskAttempt | None,
    failed: bool = False,
) -> None:
    job = locked_job(db, job_id)
    budget = db.get(JobBudget, job.id, populate_existing=True)
    unknown = failed or actual_input is None or actual_output is None
    if unknown:
        # Retain the reservation. A disconnected request may still have been billed.
        budget.unknown_usage_calls += 1
    else:
        budget.reserved_input_tokens -= reserved_input
        budget.reserved_output_tokens -= reserved_output
        budget.used_input_tokens += actual_input
        budget.used_output_tokens += actual_output
    if attempt is not None:
        previous = attempt.provider_usage or {}
        attempt.provider_usage = {
            "provider_calls": previous.get("provider_calls", 0) + 1,
            "input_tokens": previous.get("input_tokens", 0) + (actual_input or 0),
            "output_tokens": previous.get("output_tokens", 0) + (actual_output or 0),
            "unknown_usage_calls": previous.get("unknown_usage_calls", 0) + int(unknown),
        }
    event(
        db,
        job,
        "provider_call_finished",
        task=task,
        input_tokens=actual_input,
        output_tokens=actual_output,
        usage_unknown=unknown,
        failed=failed,
    )
    db.commit()


def embed_for_job(
    db: Session,
    job_id,
    texts: list[str],
    settings: Settings,
    *,
    task: ResearchTask | None = None,
    attempt: TaskAttempt | None = None,
):
    tokenizer = tiktoken.get_encoding("cl100k_base")
    estimated = sum(len(tokenizer.encode(value, disallowed_special=())) for value in texts)
    reserve_call(db, job_id, estimated, 0, task)
    try:
        result = embed_texts(texts, settings)
    except Exception:
        record_usage(db, job_id, estimated, 0, None, None, task=task, attempt=attempt, failed=True)
        raise
    actual = result[0].prompt_tokens if len(result) == 1 else result[0].batch_prompt_tokens
    record_usage(db, job_id, estimated, 0, actual, 0, task=task, attempt=attempt)
    return result


def generate_for_job(
    db: Session,
    job_id,
    prompt: str,
    response_model,
    settings: Settings,
    *,
    instructions: str,
    max_tokens: int,
    task: ResearchTask | None = None,
    attempt: TaskAttempt | None = None,
):
    # Account for schema and message framing too. This is a conservative admission
    # estimate, not a claim to know the Azure deployment's exact input tokenization.
    payload = prompt + instructions + json.dumps(response_model.model_json_schema())
    estimated = (
        round(len(tiktoken.get_encoding("o200k_base").encode(payload, disallowed_special=())) * 1.2)
        + 512
    )
    reserve_call(db, job_id, estimated, max_tokens, task)
    try:
        result = generate_structured(
            prompt,
            response_model,
            settings.model_copy(update={"max_answer_tokens": max_tokens}),
            instructions=instructions,
        )
    except Exception:
        record_usage(
            db, job_id, estimated, max_tokens, None, None, task=task, attempt=attempt, failed=True
        )
        raise
    record_usage(
        db,
        job_id,
        estimated,
        max_tokens,
        result.prompt_tokens,
        result.completion_tokens,
        task=task,
        attempt=attempt,
    )
    return result
