# GUI Modernization Plan

## Goal

Turn Vein Server Manager into a task-oriented, approachable administration
application without weakening process safety, backups, guarded configuration
writes, or background-worker requirements.

The GUI should help an operator answer three questions quickly:

1. Is the server healthy?
2. What should I do next?
3. What will change if I confirm this action?

## Experience Principles

- Prefer guided tasks over exposing implementation details.
- Present one clear primary action for the current state.
- Keep advanced controls available without making them the default workflow.
- Validate beside the affected field and explain how to resolve problems.
- Use consistent loading, empty, success, warning, and failure states.
- Keep passwords, webhooks, and other secrets protected by default.
- Run filesystem, process, network, and parsing work outside the GUI thread.
- Preserve Windows behavior while designing components for future Linux/WSL
  platform capabilities.
- Make every phase independently testable and releasable.

## Target Navigation

- **Home** - health, primary server action, players, warnings, and last backup.
- **Setup** - new/existing server, repair, and future Linux/WSL deployment.
- **Server** - identity, gameplay, networking, access, and integrations.
- **Players** - current/recent players and details.
- **Backups** - manual backup, schedules, history, retention, restore guidance.
- **Logs** - live logs, search, warnings/errors, and subsystem logs.
- **System** - diagnostics, SteamCMD, paths, updates, advanced config, and app
  preferences.

## Phases

Status during the v2.10.0 GUI work: Phase 1 is implemented. The shell now uses
one authoritative page stack, omits unfinished destinations from normal
navigation, gives Logs and Advanced Config full pages, and presents one
state-aware Set Up, Start, or Stop Server action beside explicit server state.
Monitor commands live in a compact menu with readable status. Parts of Phases
3, 4, 6, and 7 have also landed through reusable GUI modules, the Home
dashboard, scroll-safe Quick Start, status-aware process buttons, and
consolidated log views. Home now opens with an At a Glance health summary,
runtime-aware guidance, and direct Setup and Logs links. Server startup now has
a persistent progress strip that follows observable runtime milestones through
joinable readiness. The remaining items below describe the target experience,
not a claim that each phase is complete.

### Phase 1 - UX Foundation

**Status: completed baseline; continue applying it to refactored pages.**

- Add shared visual tokens and narrowly scoped application styling.
- Add reusable page headers, status badges, inline notices, and button roles.
- Standardize spacing, action hierarchy, loading, empty, and result states.
- Adopt the primitives on low-risk existing views before changing workflows.

### Phase 2 - Navigation And Application Shell

- [x] Replace duplicate main-stack/side-tab navigation with one authoritative stack.
- [x] Remove placeholder destinations from normal navigation.
- Add persistent page title/context and responsive navigation behavior.
- [x] Replace the crowded process ribbon with a state-aware primary server
  action and compact secondary/overflow actions.

### Phase 3 - Guided Quick Start

- [x] Convert the long form into a four-page wizard for Location, Identity &
  Access, Network & Integrations, and Review & Apply.
- [x] Add visible progress and preserved Back/Next form state.
- [x] Route installer-provisioned and missing servers into the wizard, existing
  unregistered servers into a compact connection flow, and completed servers
  into everyday Server Settings.
- Add immediate field validation beside the affected wizard controls.
- Show a human-readable review before expandable YAML/INI technical details.
- [x] Keep existing-install detection, protected secrets, backups, and validation.
- Default novice installs to app-managed SteamCMD and dedicated-server paths.
- Add a Network Readiness step that explains the selected UDP gameplay/query
  ports, offers explicit Windows Firewall rules, keeps the HTTP API private by
  default, and provides router port-forwarding instructions without claiming
  the app can configure every router.
- Finish with health checks, confirmed server/monitor states, LAN/public test
  guidance, and direct links to the diagnostic log when a step fails.

### Phase 4 - Everyday Operation

- [x] Build a concise Home dashboard around server health and the next action.
- Disable incompatible actions during state transitions.
  Startup and controlled shutdown now keep the primary action visibly busy
  while their helpers are active; remaining lifecycle transitions should adopt
  the same model.
- [x] Surface actionable warnings with links to the relevant repair workflow.
- [x] Present monitor health as part of server health rather than equal top-level
  process controls.

### Phase 5 - Settings And Configuration

- [x] Add focused General, Access, Gameplay, Network, and Discord settings tabs.
- [x] Retain the allowlisted INI table as a separate Advanced Settings tab.
- [x] Add unsaved-change state, refresh/discard protection, inline validation,
  batch review, a shared action footer, and restart guidance across curated tabs.
- [x] Clearly separate VEIN game-chat/admin webhooks from app notifications.
- [x] Mark curated tabs with unsaved changes and place validation feedback next
  to the affected network and Discord controls.
- [x] Preserve post-apply validation summaries and next-start/restart guidance
  through the automatic settings refresh; keep sensitive previews masked.

### Phase 6 - Logs, Backups, And Diagnostics

- Consolidate log tools into one Logs page with consistent filtering.
- [x] Give backups a history-oriented read-only page with safe restore guidance;
  keep restore unavailable until preview and current-save protection exist.
- [x] Run one shared Backup Now action off the GUI thread from Home and Backups.
- [x] Keep Home backup controls compact and route history, folder access, and
  detailed management to the dedicated Backups page.
- [x] Add guarded backup-policy controls for global enablement, implemented
  Autosave/Crash/Shutdown triggers, and independently enabled default count/age
  cleanup with a configurable minimum-backup safety floor.
- [x] Add read-only backup storage totals, oldest/newest context, and category
  filtering to archive history.
- Expand backup policy with schedules, per-category retention, restore-point
  editing/protection removal, prune previews, and storage guidance. Creating and
  filtering labeled restore points is implemented.
- Design a guarded Save Library that can load a selected save only after stopping
  the server, validating the source, and protecting the current active save.
  Read-only archive validation and destination preview are implemented; no
  restore mutation is exposed yet.
- Turn diagnostics into actionable repair cards instead of long text output.

### Phase 7 - GUI Architecture

- Reduce `Main` to application-shell orchestration.
- Move page behavior into focused controllers/view models.
- Add one reusable background task and result-reporting abstraction.
- Centralize action availability and platform capability checks.
- Keep all system mutations in shared `Controller/Tools/` modules.

### Phase 8 - Quality And Release Hardening

- Add focused helper/controller tests for every workflow.
- Add a small stable set of Qt interaction tests.
- [x] Add an isolated lifecycle integration harness with fake long-running server,
  log-monitor, and crash-monitor processes. Exercise start through joinable
  readiness, controlled shutdown, stop-flag timing, process exit, terminal
  runtime state, and protection against monitor relaunch during shutdown. The
  harness must use temporary directories and never target a real VEIN install.
- Test keyboard access, high DPI, light/dark palettes, minimum window size,
  long paths, missing files, slow work, and failure recovery.
- Perform fresh packaged-install usability tests and update screenshots.

## Delivery Strategy

Avoid a big-bang rewrite. Each phase should be delivered as small, reviewable
slices that preserve existing behavior and pass:

```text
python -m unittest discover -s Tests
Scripts\TestSuite.bat __RUN__
Scripts\RunCoverage.bat
git diff --check
```

The recommended implementation order is shared components, application shell,
Home, Quick Start wizard, Simple Server Settings, Logs/Diagnostics, Backups,
Advanced Configuration, then Linux/WSL platform integration.

## Definition Of Polished

A workflow is polished when an operator can identify its purpose, current
state, primary action, consequences, progress, and result without consulting
source code or raw configuration. Errors must be actionable, destructive or
sensitive operations must be explicit, and the application must remain
responsive throughout the workflow.
