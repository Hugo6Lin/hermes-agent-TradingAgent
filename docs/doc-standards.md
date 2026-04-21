# Documentation Standards — README and AGENT File Schema

## Purpose

Every important directory in this repository MUST have a `README.md` and (for
implementation directories) an `AGENT.md`. This file defines what each must contain.

These standards are enforced by:
1. `CONTRIBUTING.md` doc-sync rule (pre-commit warning)
2. `pytest tests/agent/research_v1/test_doc_standards.py` (repo-level check — runs in normal CI)

---

## README.md — Required Sections

Every `README.md` in a tracked directory MUST contain these sections:

### 1. What This Directory Is
> One sentence describing the purpose of this directory.

### 2. Contents / Core Files
> A table or list of the key files/modules in this directory with their purpose.

### 3. Relationship to Other Directories
> How this directory relates to sibling and parent directories. Which directories
> call this one, and which ones this one depends on.

### 4. Data Flow / How It Fits
> How data or control flows through this directory. Entry points. Exit points.

### 5. If You Modify Code Here
> A checklist of which tests and which other modules must be checked when code
> in this directory changes.

---

## AGENT.md — Required Sections

Every `AGENT.md` in a tracked implementation directory MUST contain these sections:

### 1. Responsibilities
> What this directory OWNS. Its primary purpose and scope.

### 2. Boundaries
> Explicit "Do NOT" rules for this directory. What agents must NOT do here.
> Explicit "Do" rules where non-obvious.

### 3. Key Interfaces
> The main classes/functions in this directory, their signatures, and what they return.

### 4. Upstream / Downstream
> Explicit list of modules that this directory depends on (upstream) and modules
> that depend on this directory (downstream).

### 5. Change Propagation
> A table: "If you change [file], you MUST also check [other files]."

### 6. Tests / Verification
> How to verify correctness. Test file locations. Run commands.

### 7. What NOT to Do
> Explicit list of forbidden actions specific to this directory.

---

## Directory Coverage Requirements

| Directory | Needs README | Needs AGENT |
|---|---|---|
| `agent/` | Yes | Yes |
| `agent/research_v1/` | Yes | Yes |
| `agent/research_v1/data/` | Yes | Yes |
| `agent/research_v1/analysts/` | Yes | Yes |
| `tests/` | Yes | Yes |
| `tests/agent/` | Yes | Yes |
| `tests/agent/research_v1/` | Yes | Yes |
| `docs/` | Yes | Yes |
| `.git_hooks/` | Yes | Yes |

---

## Adding a New Tracked Directory

When you create a new directory that will contain code:

1. Add it to `TRACKED_DIRS` in `.git_hooks/check_docs.py`
2. Add it to `DIRECTORIES` in `tests/agent/research_v1/test_doc_standards.py`
3. Create `README.md` following this schema
4. If implementation code (not just docs/tests): create `AGENT.md` following this schema
5. The pre-commit hook and pytest test will then enforce coverage automatically

---

## Schema Deviations

If a directory's README or AGENT cannot follow the standard schema exactly
(e.g., a directory with only one file, or a purely data directory), the file
MUST still contain the section headings (as `##` comments if empty) and a
brief note explaining why the section is not applicable.

The pytest validator checks for section heading PRESENCE, not content depth.
