# AI Native Docs

**English** | [简体中文](README.zh-CN.md)

**Help AI coding assistants find, understand, and maintain project knowledge.**

AI Native Docs is a documentation system built from four independent Skills, Markdown conventions, document templates, and Python tools. It gives project knowledge stable entry points, document identities, sources, and validation methods, helping teams preserve useful context as code changes, documentation grows, and AI assistants join the workflow.

Start with five files and expand as you add real content.

## Why AI Native Docs

Project knowledge often lives across READMEs, requirements, architecture notes, and historical records. An AI assistant can read these files, but it may not know which document is authoritative, which conclusions have been verified, or where new information belongs.

AI Native Docs provides practical conventions for these questions:

- **Minimal setup**: Initialization merges the project and documentation README/AGENTS entry points and adds one configuration file, without creating an empty category tree.
- **Grow with your content**: The first two documents in a collection share one compact file. Adding a third expands the collection into individual files and repairs references.
- **Traceable knowledge**: Documents have stable IDs and record their type, status, scope, sources, and verification evidence.
- **Preview before applying**: Initialization, synchronization, and migration can save a plan first. Applying a plan rechecks source hashes, protects local edits, and rolls back writes from the operation when a failure is recoverable.
- **Clear boundaries for facts**: Code observations produce drafts. Business meaning, approval, and command verification still require an AI assistant or a person to confirm them.
- **Local execution**: Requires Python 3.10+ and uses only the standard library. The tools do not access the network or run commands in the target project.

## Four Independent Skills

| Skill | Purpose | Main results |
| --- | --- | --- |
| [ai-docs-init](skills/ai-docs-init/SKILL.md) | Initialize a new project, onboard an existing project, or upgrade the system | Merge four entry points and save configuration, resource versions, and installation baselines |
| [ai-docs-sync](skills/ai-docs-sync/SKILL.md) | Add essential documentation from code and build manifests | Generate architecture overview and development guide drafts; safely refresh generated drafts that have no manual edits |
| [ai-docs-migrate](skills/ai-docs-migrate/SKILL.md) | Organize historical Markdown within an explicit scope | Migrate full document bodies and metadata using an explicit mapping, repair references, and leave redirects at old paths |
| [ai-docs-check](skills/ai-docs-check/SKILL.md) | Validate, find, and create documents | Check type metadata, IDs, layouts, configuration, and local references; provide shared rules and templates |

Initialization, synchronization, migration, and validation run separately. Projects with existing documentation can migrate after initialization; projects with only code can synchronize after initialization; empty projects retain the minimal structure.

## Quick Start

You need Git and **Python 3.10+**. Python 3.11+ is recommended so the synchronization tool can parse fields in `pyproject.toml` and `Cargo.toml`; on Python 3.10, it records only the locations of these TOML files.

Run the following commands from this repository's root directory in the same shell session. Replace `AI_DOCS_PROJECT` with the absolute path to your target project. Keep the plan directory outside that project.

### 1. Get the Tools

```bash
git clone https://github.com/zhzxang/ai-native-docs-skill.git
cd ai-native-docs-skill

AI_DOCS_PROJECT="/absolute/path/to/your-project"
AI_DOCS_PLAN_DIR="$(mktemp -d)"
```

### 2. Preview and Initialize

```bash
# Inspect the target project without writing changes
python3 skills/ai-docs-init/scripts/bootstrap.py --target "$AI_DOCS_PROJECT" --scan

# Preview changes and save the full plan
python3 skills/ai-docs-init/scripts/bootstrap.py \
  --target "$AI_DOCS_PROJECT" --summary \
  --plan-file "$AI_DOCS_PLAN_DIR/init.json"

# Review the changes in the plan
cat "$AI_DOCS_PLAN_DIR/init.json"

# Apply the same plan after review
python3 skills/ai-docs-init/scripts/bootstrap.py \
  --target "$AI_DOCS_PROJECT" --apply --summary \
  --plan-file "$AI_DOCS_PLAN_DIR/init.json"
```

The minimal installation for a new project:

```text
your-project/
├── README.md          # Project entry point
├── AGENTS.md          # AI execution conventions
└── docs/
    ├── README.md      # Documentation entry point
    ├── AGENTS.md      # Documentation writing conventions
    └── .ai-docs.json  # Project configuration, resource versions, and installation baselines
```

Existing entry points are merged through managed blocks, and conflicts are reported. Rules, tools, and templates stay in the Skill resource bundle; project documents are created when there is real content to add. For upgrades from an earlier full installation, see [Onboarding Existing Projects](skills/ai-docs-init/references/existing-project.md).

### 3. Synchronize Drafts from Code (Optional)

After initialization, projects with existing code can add an architecture overview and development entry points:

```bash
python3 skills/ai-docs-sync/scripts/sync.py \
  --target "$AI_DOCS_PROJECT" \
  --plan-file "$AI_DOCS_PLAN_DIR/sync.json"

cat "$AI_DOCS_PLAN_DIR/sync.json"

python3 skills/ai-docs-sync/scripts/sync.py \
  --target "$AI_DOCS_PROJECT" --apply \
  --plan-file "$AI_DOCS_PLAN_DIR/sync.json"
```

When supporting source facts are available, the tool generates `architecture-overview` and `development-guide` drafts. It records observable code paths and manifest declarations. Module responsibilities, business boundaries, data flows, and command meanings require further code review. Commands found in manifests are neither run automatically nor marked as verified automatically.

### 4. Validate Documentation

```bash
# Check types, structure, IDs, and local references
python3 skills/ai-docs-check/scripts/check.py --root "$AI_DOCS_PROJECT" check

# Also check project configuration and verification readiness
python3 skills/ai-docs-check/scripts/check.py --root "$AI_DOCS_PROJECT" check --strict
```

After a minimal installation, strict checks may still report missing configuration or verification evidence. A completed installation, valid structure, and strict readiness are three distinct outcomes. Validation failures return a nonzero exit code for use in automated checks.

## Use with an AI Assistant

Place the Skill directories you need in a Skill discovery directory supported by your AI client. Include `ai-docs-check` alongside them and preserve this layout:

```text
<skills-directory>/
├── ai-docs-init/
├── ai-docs-sync/
├── ai-docs-migrate/
└── ai-docs-check/
    └── assets/templates/
```

You can also ask an assistant to read the relevant `SKILL.md` in this repository and run its scripts directly. Keeping files in a repository does not install them globally; automatic discovery depends on the client.

Example requests:

```text
Use ai-docs-init to initialize a minimal documentation system for this project. Show me the change plan first.
Use ai-docs-sync to read the code and add architecture overview and development guide drafts.
Use ai-docs-migrate to migrate Markdown in legacy/, preserving full content and repairing references.
Use ai-docs-check to validate the documentation changed in this task and report structural issues and facts awaiting verification.
```

By default, resources come from the adjacent `ai-docs-check/assets/templates/` directory. With a different layout, use `--source` to specify the resource root for initialization, synchronization, and migration, or `--resources` for validation. The resource version must match `system.version` in the target configuration.

For examples of client entry point adapters, see [Tool Adapters](skills/ai-docs-check/assets/templates/docs/_system/tool-adapters.md).

## Ongoing Maintenance and Historical Migration

Search for existing documents before updating or creating one:

```bash
python3 skills/ai-docs-check/scripts/check.py --root "$AI_DOCS_PROJECT" find --type feature
python3 skills/ai-docs-check/scripts/check.py --root "$AI_DOCS_PROJECT" route feature
python3 skills/ai-docs-check/scripts/check.py --root "$AI_DOCS_PROJECT" \
  new feature FEAT-001 login --title "Login"
```

New documents still need real content and evidence. You can validate a candidate file independently before writing it into a project, without initializing its directory first:

```bash
python3 skills/ai-docs-check/scripts/check.py check-meta /absolute/path/to/candidate.md
```

For historical migration, inspect the files first, define a mapping from old paths to document types, IDs, and slugs, then preview and apply the same plan:

```bash
python3 skills/ai-docs-migrate/scripts/migrate.py --target "$AI_DOCS_PROJECT" --scan
```

See the [Migration Guide](skills/ai-docs-migrate/references/migration.md) for the full mapping format, preview and apply commands, and supported Markdown formats. Migration scope must be explicit; the script does not infer business categories.

Plan files never overwrite existing files. If the target or source changes, generate a new plan with a new filename. Synchronization and migration require a saved plan when using `--apply`.

## How Documents Are Organized

The documentation conventions cover project, product, design, engineering, API, data, testing, release, operations, security, and other knowledge areas, with **72 document types** currently available. See the [meta schema](skills/ai-docs-check/assets/templates/docs/_system/meta-schemas.json) for type definitions and [collections.json](skills/ai-docs-check/assets/templates/docs/_system/collections.json) for collection routing.

| Collection contents | Layout |
| --- | --- |
| No entries | No project document files or directories are created |
| 1–2 entries | `<base_path>.md`, with a separate ID, metadata, and body for each entry |
| From the third entry | `<base_path>/ID-slug.md`; existing entries are expanded and references repaired |
| Already expanded | The directory remains; it is not collapsed automatically |

The project charter, architecture overview, and development guide each use a standalone document path. Document statuses include `draft`, `active`, `deprecated`, and `archived`. Unknown facts remain `null`; passing format checks does not mean the content has been approved or business behavior has been verified.

For the detailed design, see [Adaptive Documentation Architecture](docs/architecture.md).

## Repository Structure and Development

### Local Scenario Evaluations

The local evaluation harness and project fixtures live in [`evals/`](evals/README.md). Fourteen scenarios cover a scaffolded Vite Todo, Python CLI, historical Markdown, and an empty project. Todo scenarios include writing product documentation, adding editing, and repairing an injected completion bug, with independent behavior and browser checks. Each Codex CLI attempt runs in a fresh copy, with independent checks for files, metadata, facts, and modification scope. The default model follows your current CLI configuration. Inputs and reports stay local; model execution requires normal service connectivity and consumes the applicable usage allowance.

```bash
python3 evals/run.py list
python3 evals/run.py run --engine tools       # Script smoke checks without a model
python3 evals/run.py run --case vite-init     # A real Codex scenario
python3 evals/run.py run --tag vite --repeat 3
# Prepare local dependencies, then run the three Todo development scenarios
npm ci --prefix evals/fixtures/vite-todo
python3 evals/run.py run --tag todo-development --timeout 1200
```

Reports, event logs, final project files, and diffs are saved under `evals/results/`. See the [local evaluation guide](evals/README.md) for commands, project imports, and assertion formats.

```text
.
├── README.md                    # English
├── README.zh-CN.md               # 简体中文
├── docs/architecture.md          # Design documentation
├── evals/                       # Local fixtures, scenarios, and runner
├── tests/                       # Skill and protocol regression tests
└── skills/
    ├── ai-docs-init/
    ├── ai-docs-sync/
    ├── ai-docs-migrate/
    └── ai-docs-check/            # Validation entry point and shared resources
        └── assets/templates/    # Single source for conventions, entry points, type templates, and tools
```

Maintain shared rules, templates, and runtime tools directly in `skills/ai-docs-check/assets/templates/`. This directory is the single source used by all four Skills and is distributed with `ai-docs-check`; no copy or build step is required. Skill and protocol regression tests are collected in `tests/`, outside the Skill resources.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
python3 skills/ai-docs-check/scripts/check.py --root skills/ai-docs-check/assets/templates check
```

Evaluation harness tests remain in `evals/`; run them as described in the [local evaluation guide](evals/README.md).

Issues and pull requests with bug reports and improvements are welcome. Keep the English and Chinese READMEs in sync when editing documentation. For system changes, run the relevant tests and resource structure checks. These tests validate the documentation system itself; run the target project's business tests separately.
