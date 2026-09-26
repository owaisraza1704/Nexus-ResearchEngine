# Research execution: what is implemented and what is measured

The repository supports asynchronous research through Celery, PDF/DOCX/DOC ingestion,
approved web-page ingestion, bounded query decomposition, parallel retrieval branches,
keyword/vector hybrid retrieval, and cited reports. These paths have been exercised through
the real local API and browser, using the configured Azure deployments.

It does **not** currently establish a 50% reduction in comprehensive report generation time.
Redis prompt/response caching and the proposed 35% token reduction are not implemented.
Redis is the Celery broker only.

## Labeled retrieval evaluation: 26 September 2026

The existing dataset has 20 curated questions and relevance labels for passages in one
55-chunk architecture PDF. The same ready document snapshot, Azure embedding deployment,
and `top_k=5` were used for vector-only and hybrid retrieval. `ir_measures` calculated
the metrics from the returned rankings; these are retrieval scores, not answer-quality
or faithfulness scores. Each strategy was run separately against the same labels.

| Metric | Vector-only | Hybrid |
| --- | ---: | ---: |
| Recall@1 | 0.6433 | 0.4183 |
| Recall@3 | 0.8800 | 0.7117 |
| Recall@5 | 0.9317 | 0.8300 |
| MRR@5 | 0.9000 | 0.7267 |
| nDCG@5 | 0.8896 | 0.7115 |

Hybrid missed every labeled relevant passage in two questions at `top_k=5`; vector-only
did not do so for any question. On this corpus, the current hybrid ranking regresses.
The dataset is small and single-document, so it cannot establish which strategy works
best for other source types or larger research collections. The raw
[vector](benchmarks/2026-09-26-retrieval-vector.json) and
[hybrid](benchmarks/2026-09-26-retrieval-hybrid.json) records include each question's
retrieved chunk sequences.

DeepEval and Ragas were **not** used here. They may be useful for a separate,
independently reviewed answer-quality evaluation, but an LLM judge score is not a
substitute for these labeled retrieval rankings or for manual citation review.

## Repeated end-to-end comparison: 26 September 2026

A second real-Azure batch used the same synthetic PDF/DOCX sources, question, model,
hybrid retrieval and limits within the batch. It recorded one warm-up per variant,
then five alternating pairs with `max_parallel_tasks=1` versus `2`. Persisted job
creation-to-completion time includes planning, queueing, embedding, retrieval,
synthesis and validation, but excludes ingestion and browser polling.

| Pair | One-task limit | Two-task limit |
| --- | ---: | ---: |
| 1 | 15.784 s | 16.440 s |
| 2 | 13.863 s | 14.999 s |
| 3 | 16.123 s | 16.257 s |
| 4 | 16.009 s | 16.412 s |
| 5 | 18.308 s | 17.248 s |
| Median | **16.009 s** | **16.412 s** |

The two-task variant was **2.52% slower by median complete-job time** in this batch.
Retrieval branches overlapped in all five two-task runs and none of the one-task runs.
The median wall-clock span of the two retrieval tasks was 3.373 s versus 1.746 s,
an observed 48.2% shorter retrieval stage. Median synthesis was 7.900 s versus
9.659 s, however, and all ten generated plans had different hashes. The task overlap
is verified, but neither the stage nor end-to-end difference is a controlled causal
estimate of the parallelism limit's effect.

All ten measured jobs ended `completed_with_gaps`: each had a report, cited both
synthetic sources, and passed exact evidence excerpt/locator checks; each also
reported unresolved gaps. These checks do **not** establish that every claim is
semantically correct. Timings, plans, task intervals and usage are in the
[five-pair benchmark record](benchmarks/2026-09-26-five-pairs.json). Its local
workspace ID is `e059fc94-0d66-4b90-9923-34b6b6d49773`.

## Earlier local observation: 26 September 2026

The same synthetic PDF/DOCX source snapshots, question, model, hybrid strategy and context
limits were used throughout the measured batch. Only the requested parallel-task limit
changed: one versus two. The Docker worker had two prefork execution slots. No other
research jobs, builds or backend test suites ran during the measurements.

One warm-up per variant was recorded separately, followed by three alternating pairs:
sequential/parallel, parallel/sequential, sequential/parallel. Times below use the persisted
job creation and completion timestamps. They include queueing, planning, embedding,
retrieval, synthesis and validation; document ingestion and browser polling are excluded.

| Pair | Sequential | Parallel |
| --- | ---: | ---: |
| 1 | 17.754 s | 13.260 s |
| 2 | 19.066 s | 15.659 s |
| 3 | 18.384 s | 16.985 s |
| Median | **18.384 s** | **15.659 s** |

The parallel variant had an **observed 14.82% lower median elapsed time in that batch**.
The five-pair batch above did not reproduce an end-to-end improvement. Both retrieval
branches overlapped in every measured parallel run; none overlapped in the sequential
runs. All six runs produced validated reports with citations to both sources, and exact
evidence text/locators were checked against their saved chunks. Explicit gaps are valid
results, not execution failures.

This is a small end-to-end observation, **not a causal or general performance guarantee**:

- There were only three samples per variant on a small, two-document corpus.
- All six model-generated plans had different hashes, despite addressing the same two
  aspects. Generated report lengths and Azure latency also varied.
- Synthesis alone took 7.273–10.952 seconds. Planning and synthesis are still sequential
  parts of the pipeline; parallel retrieval does not halve the whole workflow.
- The baseline is this implementation with one task slot, not a measured historical release.
- ranx uses Numba and has a cold compilation/import cost. Warm-up timings are recorded but
  excluded from the table; these are not first-request latency claims.
- Citation identity and source scope were checked. That is not an independent semantic
  correctness assessment of every generated claim.
- There is no application prompt cache. Provider-side optimizations, if applied by Azure,
  are outside this comparison; no token-savings attribution is made.

Raw timings, task intervals, plans, usage and source snapshot IDs are retained in
[the benchmark record](benchmarks/2026-09-26-local.json). The workspace is
`bbb756ea-7da5-4080-8d90-0eee562a5bc3` and remains inspectable in the local UI.

An initial cold warm-up exposed an overly strict benchmark assertion: it rejected a valid
`completed_with_gaps` report. The harness was fixed, two regression tests were added, and
the entire measured batch was restarted. The initial check is retained in
[the preflight record](benchmarks/2026-09-26-preflight.json); it was not a discarded measured
sample. Research behavior was not changed to make that assertion pass.

## Reproduce

Start the local stack and install development dependencies. This command makes billable
Azure calls, creates a labeled workspace, and keeps its sources and runs:

```sh
uv run python -m evals.retrieval --strategy vector \
  --output .data/benchmarks/retrieval-vector.json
uv run python -m evals.retrieval --strategy hybrid \
  --output .data/benchmarks/retrieval-hybrid.json
uv run python scripts/benchmark_research.py --pairs 5 \
  --output .data/benchmarks/local-comparison.json
```

Keep the machine and research queue otherwise idle. For a defensible percentage claim,
use a larger representative workload, control or replay identical plans, run more repeated
pairs, and independently check that report quality has not regressed. Do not select only
the fastest parallel runs or count retrieval-only savings as complete-report savings.

## Accurate capability wording

> Built a local asynchronous agentic RAG research platform that ingests PDF, DOCX, legacy
> DOC and explicitly approved web content, decomposes complex questions into parallel
> research tasks through Celery workers, combines keyword and vector retrieval, and
> synthesizes evidence-grounded reports with inspectable source attribution.

Keep fixed 50% runtime and 35% token-reduction claims out until suitable measurements and,
for the latter, an actual caching implementation support them.
