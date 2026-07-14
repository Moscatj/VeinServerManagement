# Documentation Maintenance

This guide keeps project documentation accurate, readable for people, and
useful as durable context for AI-assisted development. `AGENTS.md` remains the
authority for AI behavior and permissions.

## Principles

- Documentation changes ship with the behavior they describe.
- One document owns each policy or detailed explanation; other pages link to it.
- Current behavior and future intent are labeled separately.
- Generic examples use placeholders such as `vX.Y.Z` instead of a release that
  will become stale.
- Historical release notes, dated audit markers, and measured baselines are not
  rewritten merely because a new version exists.
- Instructions should be task-oriented, concise, and understandable without
  reading source code.

## Ownership Matrix

| Change | Documents to review |
|---|---|
| User-facing capability or workflow | `README.md`, `CHANGELOG.md`, relevant operator guide |
| Installer or packaged behavior | `README.md`, `Docs/packaging_overview.md`, `ROADMAP.md` |
| GUI navigation or workflow | `Docs/vein_manager_summary.md`, `Docs/gui_modernization.md`, `Docs/quick_start.md` |
| Config key/default/path | `Config/config.example.yaml`, `Docs/config_reference.md`, config summaries |
| Lifecycle, monitor, or backup behavior | matching controller summary, `Docs/control_layer_overview.md`, safety guidance when relevant |
| New or completed roadmap feature | `ROADMAP.md`, relevant phase/design document, `CHANGELOG.md` |
| Test/coverage policy or measured baseline | `Docs/testing.md`, `Docs/coverage_strategy.md`, `AGENTS.md` when the gate changes |
| AI/contributor workflow | propose first; after approval update `AGENTS.md`, this guide, `CONTRIBUTING.md`, and affected GitHub templates |
| Commit/push/CI workflow | `Docs/publishing_workflow.md`, `AGENTS.md`, `CONTRIBUTING.md`, CI workflow |
| Subsystem ownership/routing or new Python module/test | `Docs/subsystems.yaml`, affected summary/reference pages |
| Cross-cutting architecture decision | add or supersede a record under `Docs/decisions/`; link current guidance |
| Release/version | current-version sweep below, `CHANGELOG.md`, `RELEASING.md` |

Not every listed file must change. Each must be reviewed, and unchanged files
should remain accurate.

## Release-Time Version Sweep

The release task should update current-release declarations automatically as
part of the release commit:

1. Move `CHANGELOG.md` entries from `Unreleased` into the dated release section.
2. Update the current stable/baseline version in:
   - `README.md`
   - `ROADMAP.md`
   - `RELEASING.md`
   - `Docs/_index.md`
   - `Docs/docs_for_codex.md`
3. Search all Markdown for the previous version and classify each match:
   - update current-state claims;
   - preserve historical changelog/release-table entries;
   - preserve dated “audited against” or measured-coverage markers unless a new
     audit or measurement was actually performed;
   - replace versioned examples with `vX.Y.Z` when the exact number is not
     meaningful.
4. Confirm `ROADMAP.md` describes newly delivered features as implemented and
   retains only unfinished work under future goals.
5. Run the documentation/version consistency gate with the intended tag. The
   newest dated `CHANGELOG.md` release is the authoritative version for the
   current-version declarations:

   ```powershell
   python Controller\Tools\documentation_check.py --tag vX.Y.Z
   ```

   The gate rejects a tag/changelog mismatch, missing or conflicting baseline
   declarations, duplicate or misordered changelog versions, missing release
   notes, and hardcoded installer-version examples.
6. Run link, stale-reference, and `git diff --check` validation before tagging.

A useful discovery command is:

```powershell
rg -n -g '*.md' 'v[0-9]+\.[0-9]+\.[0-9]+|[0-9]+\.[0-9]+\.[0-9]+' .
```

Review the matches; do not use an unreviewed global replacement.

Normal push and pull-request CI runs the checker without `--tag`. The tagged
installer workflow supplies the actual Git tag and must pass before packaging.

## Roadmap Hygiene

When a feature or phase is completed:

- add it to the current baseline or mark its status clearly;
- remove or rewrite future-tense bullets that are now implemented;
- retain unfinished follow-up work as specific next steps;
- keep known limitations factual for the current release;
- avoid turning the roadmap into a duplicate changelog.

The changelog records what shipped. The roadmap records current maturity,
remaining work, and direction.

## AI Workflow Improvements

AI assistants should actively mention opportunities to simplify instructions,
improve validation, reduce repeated context, or clarify ownership. Suggestions
should include the problem, proposed change, benefit, and tradeoff.

Workflow suggestions are proposals only. Changes to AI permissions, approval
behavior, testing requirements, release rules, or contributor governance must
wait for explicit user approval. Ordinary documentation updates required by an
already-approved feature do not require a separate workflow approval.

## Readability Checklist

- Is the intended audience clear?
- Does the page describe current behavior accurately?
- Are future capabilities explicitly labeled?
- Is detailed content owned in one place and linked elsewhere?
- Are commands, paths, links, and version claims valid?
- Can obsolete examples, repeated warnings, or generated-looking boilerplate be
  removed?
- Were secrets, private paths, saves, logs, and local configuration excluded?
