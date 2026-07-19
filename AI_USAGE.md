# AI Usage Disclosure

## Tools Used

| Model | Usage Share | Role |
|---|---|---|
| **Google Gemini 3.5 Flash** (medium thinking) | ~60% | Primary implementation — code generation, first-pass design, DAG and parser scaffolding |
| **Google Gemini 3.1 Pro** (low thinking) | ~30% | Continued implementation after Flash credit exhaustion — SQL models, API endpoints, dbt layer |
| **Anthropic Claude Sonnet 4.6** (thinking mode) | ~10% | Final code review, bug identification, targeted fixes, this document |

Model selection was guided by credit optimization: I consulted ChatGPT on which models to use, and — working from a promo account with no visibility into remaining credit — chose lower-usage models (Flash/Pro with reduced thinking budgets) for as long as output quality was acceptable. The switch to Claude Sonnet at the end was made when a final review pass required stronger reasoning and remaining credit was less of a concern.


---

## My Approach & Process

### Starting Point: AI-Generated Implementation Plan

Before writing any code, I asked an LLM to generate a detailed implementation plan (`execution_plan.md`). I read it carefully before acting on it. The plan had several issues that I identified and chose to deviate from:

1. **`pandas` for Excel parsing** — The plan suggested using `pandas` to read the `.xlsm` files. This is a common but poor recommendation for structured financial Excel files: pandas' type inference silently coerces numeric values and struggles with non-tabular key-value layouts. I used `openpyxl` directly instead, giving full control over cell-level parsing.

2. **`postgres:15-alpine` base image** — Alpine-based images are generally discouraged in production due to missing C libraries (`musl` vs `glibc`) that can cause subtle compatibility issues. Not critical for a standalone Postgres container, but a signal that the plan was not production-aware.

3. **Airflow 2.9 instead of 3.x** — The plan suggested `apache/airflow:2.9.0`. Airflow 3 was already available and represents a significant architectural improvement (new task execution model, improved SDK). Using an outdated major version would have been a poor choice for a "production-ready" submission.

4. **No suggestion to start from the official Airflow docker-compose** — Apache Airflow publishes an official `docker-compose.yaml` that correctly configures the scheduler, webserver, triggerer, and worker with proper healthchecks and volume mounts. Starting from scratch, as the plan implied, would have wasted significant time and introduced configuration errors. I downloaded the official compose file and simplified it to fit the project's needs.

5. **No mention of dbt** — The plan proposed raw SQL ingestion scripts and Alembic migrations for schema management. Using dbt for the transformation layer is a significantly better pattern: it gives version control, lineage, documentation, and testability for free. The plan missed this entirely.

### Incremental Delivery Strategy

Given the task deadline, I deliberately chose an **incremental delivery strategy** rather than following the plan's waterfall-style epic sequence:

1. Start with the official Airflow docker-compose as the infrastructure foundation
2. Get a working end-to-end pipeline (extract → load → basic API) as quickly as possible
3. Iterate and add correctness (bitemporality, versioned idempotency, validation framework)
4. Refactor multiple times as the design became clearer

This ensured there was always a working, demonstrable state at each step — a risk mitigation approach under deadline pressure, and the same approach I would take in a production sprint.


---

## Conversation Logs (Phase 1)

Two Gemini conversations are attached alongside this document, covering the bulk of implementation work:

### `Fixing Rating Parser Issues.md` (~36 turns)
<>
Covers debugging and redesigning the Excel parser. Representative exchanges:

**User identifying bugs proactively (before asking AI to fix them):**
> *"I checked the parser and the files found several problems: 1. the credit metrics data is not parsed — this one contains the actuals and estimated financial metrics. 2. some ranges seem to be wrongly defined (refer to column D instead of C, example: End of Business Year). What solutions do you have for these problems? First just write, do not implement."*

**User driving feature design — not accepting the first proposal:**
> *"I think that we need to do the following: 1. have the logic versioned — some file versions might be like this, other ones might be correct. We can make a decision rule to see what version the file is. [...] 2. We definitely need all the rows in the financial data, with a split for actuals and estimated. 3. And also a check that no other data points are in the sheet. If there are, we should probably fail the DAG, with an error message indicating which cells are the problem."*

### `Refactoring Corporate Ratings Staging.md` (~129 turns)

Covers the dbt layer design, bitemporality, API development, and validation framework. Representative exchanges:

**On column naming precision:**
> *"Yes, but I think the column `is_latest_business_version` should be `is_latest_business_version_for_year_actuals` (or something similar). What do you think?"*

**On the bitemporal edge case — late-arriving corrected data:**
> *"But what if we have v2 with value 10 for 2024 (last year actuals) and v3 has actuals for 2024 and 2025, but 2024 is corrected to 10.1?"* → Led to the SCD partitioning decision documented in `DESIGN_DECISIONS.md`.

**Challenging AI on `as_of_date` semantics with an external reference:**
> *"This is what ChatGPT says — it kind of contradicts what you said before. Which is true? Back it up with references. Usually, 'as of date' refers to the point in time that the financial statements describe, not the information that happened to be available on that date."*

**On validation approach — pushing back explicitly against lenient design:**
> *"On one side I like option B to be user-friendly, but this just encourages analysts to upload bad data and lets us handle edge cases with yet another `CASE WHEN`, which makes the code ugly and hard to maintain. Should we go for option A and document it? We have an errors field, no?"*

**On API design and pagination — scoping correctly for MVP vs production:**
> *"Limit and offset should be for all endpoints that return arrays in production. Should we add it here, or just document what we would do in production?"*

**On SQL injection — proactively raising a security concern:**
> *"Did you take care of SQL injection?"*

**On port selection — flagging a practical infrastructure concern:**
> *"Is port 8000 or 8080 a good idea?"* (Context: on a shared development machine with multiple running containers, default ports like 8000/8080 are commonly occupied. This was flagging a real operational concern, not a basic question.)

**On the uploads endpoint response design:**
> *"GET /uploads: you return not only the metadata, but actual payload data too — `parsed_payload` repeats most of the fields from above. What is a proposed improvement?"*

**On operational cleanup — pragmatic decision under time pressure:**
When the pipeline broke mid-session, the decision was made to tear down and rebuild the full stack rather than debug state incrementally: *"I ran `make down`, removed the data, then `make up` and `make seed`."* (This reflects a deliberate speed/reliability tradeoff during a deadline-driven task, not an inability to debug — the root cause was subsequently identified and fixed.)


---

## Working Method

The project had two distinct phases with different AI-interaction patterns.

### Phase 1 — Implementation (~90% of total work, Gemini models)

AI was the **primary code author**. The workflow was:

1. Specify the requirement or component to build
2. AI generates the code
3. Review the output, identify problems, challenge design decisions
4. Ask for changes or refinements — from naming conventions to significant architectural decisions
5. Repeat until acceptable

Approximately **90–95% of the code was AI-generated**. My contribution in this phase was: requirements specification, architectural direction, challenging outputs that were wrong or suboptimal, enforcing naming conventions, translating business expectations into technical requirements, and making the design decisions documented in `DESIGN_DECISIONS.md`.

Examples of decisions made during this phase that shaped the final design:
- Rejecting `pandas` for Excel parsing in favour of direct `openpyxl` cell-level access
- Choosing Airflow 3.x over the AI-suggested 2.9
- Adopting the official Airflow docker-compose as the foundation
- Introducing dbt (not suggested by the initial plan)
- The bitemporal SCD design, including partitioning by `(company_name, max_actual_year)` to handle late-arriving data
- The schema-driven parser with `parser_sha` + `schema_sha` versioned idempotency

### Phase 2 — Review & Cleanup (~10% of total work, Claude Sonnet 4.6)

With a working codebase, the workflow shifted to **code review**:

1. Ask AI to review existing implementation against requirements — high level first, no testing
2. Receive structured findings (bugs, design issues, leftover code)
3. Apply a subset of the suggestions independently
4. Ask for a second-pass review of the changes
5. Ask AI to implement the remaining targeted fixes


### Documentation
This document was written with AI assistance in Phase 2.

---

## Summary

| Component | AI Contribution | Engineer Contribution |
|---|---|---|
| ~90-95% of code | Generated | Specified, reviewed, directed |
| Architecture & design decisions | Proposed (often rejected or revised) | Final decisions and rationale |
| Initial implementation plan | Generated | Critically evaluated; several points rejected |
| Phase 2 bug fixes | Identified and implemented | Reviewed and approved |
| `DESIGN_DECISIONS.md` | None | Written independently |
| This document | Written with assistance | Directed and corrected for accuracy |
