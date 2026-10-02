# AI Native Docs

[简体中文](README.md) | **English**

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

## Installation

You need **Node.js (including npm/npx)** and Git. Running the Skill tools requires **Python 3.10+**. Python 3.11+ is recommended so the synchronization tool can parse fields in `pyproject.toml` and `Cargo.toml`.

Install all four Skills with the [Skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add zhzxang/ai-native-docs-skill \
  --skill ai-docs-init ai-docs-sync ai-docs-migrate ai-docs-check \
  --global
```

Follow the prompts to select your AI client. `--global` installs the Skills in your user directory for reuse across projects and keeps shared resources outside the target project, as required by the migration tool. After installing the Skills, invoke them in the target project to create its documentation entry points.

If you only need initialization, install the minimal combination. Include `ai-docs-check`, which provides the shared rules, templates, and tools:

```bash
npx skills add zhzxang/ai-native-docs-skill \
  --skill ai-docs-init ai-docs-check --global
```

List available and installed Skills:

```bash
npx skills add zhzxang/ai-native-docs-skill --list
npx skills list --global
```

See the [official Skills CLI documentation](https://github.com/vercel-labs/skills#options) for more installation options.

## Quick Start

After installation, make the following requests to your AI assistant in the target project.

### 1. Initialize a Minimal Documentation System

```text
Use ai-docs-init to initialize a minimal documentation system for this project. Show me the change plan first.
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

### 2. Add Documentation for Your Project (Optional)

For projects with existing code, synchronize architecture overview and development guide drafts:

```text
Use ai-docs-sync to read the code and add architecture overview and development guide drafts.
```

For projects with historical Markdown, define the scope before migrating:

```text
Use ai-docs-migrate to migrate Markdown in legacy/, preserving full content and repairing references.
```

Synchronized drafts record observable code paths and manifest declarations. Module responsibilities, business boundaries, data flows, and command meanings require further code review. Commands found in manifests are neither run automatically nor marked as verified automatically.

### 3. Validate Documentation

```text
Use ai-docs-check to validate the documentation changed in this task and report structural issues and facts awaiting verification.
```

After a minimal installation, strict checks may still report missing configuration or verification evidence. A completed installation, valid structure, and strict readiness are three distinct outcomes. Validation failures return a nonzero exit code for use in automated checks.

## Run Scripts Manually (Optional)

You can also run the installed Python tools directly. Run the following commands in the same shell session. Replace `AI_DOCS_SKILLS` with the actual parent directory containing the four Skills, as shown in the installation output, and `AI_DOCS_PROJECT` with the absolute path to your target project. Keep the plan directory outside that project.

```bash
AI_DOCS_SKILLS="/absolute/path/to/installed/skills"
AI_DOCS_PROJECT="/absolute/path/to/your-project"
AI_DOCS_PLAN_DIR="$(mktemp -d)"
```

You can also point `AI_DOCS_SKILLS` to the absolute path of `skills/` in this source repository.

### Preview and Initialize

```bash
# Inspect the target project without writing changes
python3 "$AI_DOCS_SKILLS/ai-docs-init/scripts/bootstrap.py" --target "$AI_DOCS_PROJECT" --scan

# Preview changes and save the full plan
python3 "$AI_DOCS_SKILLS/ai-docs-init/scripts/bootstrap.py" \
  --target "$AI_DOCS_PROJECT" --summary \
  --plan-file "$AI_DOCS_PLAN_DIR/init.json"

# Review the changes in the plan
cat "$AI_DOCS_PLAN_DIR/init.json"

# Apply the same plan after review
python3 "$AI_DOCS_SKILLS/ai-docs-init/scripts/bootstrap.py" \
  --target "$AI_DOCS_PROJECT" --apply --summary \
  --plan-file "$AI_DOCS_PLAN_DIR/init.json"
```

### Synchronize Drafts from Code After Initialization

```bash
python3 "$AI_DOCS_SKILLS/ai-docs-sync/scripts/sync.py" \
  --target "$AI_DOCS_PROJECT" \
  --plan-file "$AI_DOCS_PLAN_DIR/sync.json"

cat "$AI_DOCS_PLAN_DIR/sync.json"

python3 "$AI_DOCS_SKILLS/ai-docs-sync/scripts/sync.py" \
  --target "$AI_DOCS_PROJECT" --apply \
  --plan-file "$AI_DOCS_PLAN_DIR/sync.json"
```

### Validate Documentation

```bash
# Check types, structure, IDs, and local references
python3 "$AI_DOCS_SKILLS/ai-docs-check/scripts/check.py" --root "$AI_DOCS_PROJECT" check

# Also check project configuration and verification readiness
python3 "$AI_DOCS_SKILLS/ai-docs-check/scripts/check.py" --root "$AI_DOCS_PROJECT" check --strict
```

### Locate Shared Resources

Keep the four Skill directories next to each other, with the complete resources included in `ai-docs-check`:

```text
<skills-directory>/
├── ai-docs-init/
├── ai-docs-sync/
├── ai-docs-migrate/
└── ai-docs-check/
    └── assets/templates/
```

By default, resources come from the adjacent `ai-docs-check/assets/templates/` directory. With a different layout, use `--source` to specify the resource root for initialization, synchronization, and migration, or `--resources` for validation. The resource version must match `system.version` in the target configuration.

For examples of client entry point adapters, see [Tool Adapters](skills/ai-docs-check/assets/templates/docs/_system/tool-adapters.md).

## Ongoing Maintenance and Historical Migration

Search for existing documents before updating or creating one:

```bash
python3 "$AI_DOCS_SKILLS/ai-docs-check/scripts/check.py" --root "$AI_DOCS_PROJECT" find --type feature
python3 "$AI_DOCS_SKILLS/ai-docs-check/scripts/check.py" --root "$AI_DOCS_PROJECT" route feature
python3 "$AI_DOCS_SKILLS/ai-docs-check/scripts/check.py" --root "$AI_DOCS_PROJECT" \
  new feature FEAT-001 login --title "Login"
```

New documents still need real content and evidence. You can validate a candidate file independently before writing it into a project, without initializing its directory first:

```bash
python3 "$AI_DOCS_SKILLS/ai-docs-check/scripts/check.py" check-meta /absolute/path/to/candidate.md
```

For historical migration, inspect the files first, define a mapping from old paths to document types, IDs, and slugs, then preview and apply the same plan:

```bash
python3 "$AI_DOCS_SKILLS/ai-docs-migrate/scripts/migrate.py" --target "$AI_DOCS_PROJECT" --scan
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
├── README.md                    # 简体中文 (default)
├── README.en.md                 # English
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
