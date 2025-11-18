# Contributing to Vein Server Management

Thanks for your interest in contributing!

This project is a Windows-focused management suite for the **Vein** dedicated server.  
It is being hardened with the goal of eventual open-source release.

---

## 1. Repo Layout (Quick Reminder)

- Python logic:
  - `Controller/*.py` (core scripts)
  - `Controller/Tools/*.py` (helper modules)
- Config:
  - `Config/config.yaml` (primary)
  - `Config/Backup/` (legacy backups/samples)
- Scripts:
  - `Scripts/*.bat` (Windows entrypoints)
- Runtime state:
  - `Runtime/` (PID files, JSON flags; auto-created)
- Logs / Backups:
  - `Logs/`
  - `Backups/`

See `README.md` and `Docs/_index.md` for more detail.

---

## 2. Getting Started

Clone the repo:

```bash
git clone https://github.com/<YOUR_USERNAME>/VeinServerManagement.git
cd VeinServerManagement
Python Environment
This project expects a reasonably recent Python (3.11+ recommended).

Create a virtual environment (optional but recommended):

bash
Copy code
python -m venv .venv
.\.venv\Scripts\activate    # PowerShell / cmd on Windows
Install the libraries used by the controller scripts (examples):

PySide6

PyYAML

requests

Any others referenced in Controller/*.py and Controller/Tools/*.py

For a more complete list, consult Docs/Developer_Guide.md and inspect imports in the controller modules.

3. Basic Usage (for contributors)
From the repo root:

bash
Copy code
# Start GUI
python Controller/vein_manager.py

# Start server
python Controller/start_server.py

# Start monitors
python Controller/crash_monitor.py
python Controller/monitor_log.py

# Clean shutdown
python Controller/shutdown_server.py
Or use the batch files under Scripts/:

bat
Copy code
Scripts\env_setup.bat
Scripts\StartServer.bat
Scripts\StartAllMonitors.bat
Scripts\Start_VeinManager.bat
Scripts\StopServer.bat
4. Coding Guidelines
Target Python 3.11+.

Keep functions and modules focused and small.

Prefer:

Controller/utils.py for high-level shared helpers.

Controller/Tools/*.py for lower-level or reusable pieces.

Use Controller/config.py + Controller/config_helper.py for config access.

Avoid introducing new global state; prefer explicit parameters or config-driven behavior.

If you touch shutdown / crash / backup logic, read:

Controller/shutdown_server.py

Controller/utils.py

Docs/control_layer_overview.md

Docs/Developer_Guide.md

5. Pull Request Workflow
Fork the repo.

Create a feature branch:

bash
Copy code
git checkout -b feature/my-change
Make your changes:

Keep them as small and self-contained as possible.

Update docs (Docs/*.md, README.md) if behavior or config surface changes.

Run the scripts you touched at least once to ensure they don’t crash immediately.

Open a PR with:

A clear description of the change

Notes on any risk to:

shutdown behavior

backups

crash/monitor logic

6. Using AI (Codex, ChatGPT, Copilot) on This Repo
This project explicitly supports AI-assisted development.

If you use AI on this repo:

Ensure it reads AGENTS.md first.

Verify it understands:

Python lives in Controller/ and Controller/Tools/.

Config is Config/config.yaml (with JSON legacy support).

Review AI-generated changes as if they were from a junior contributor:

Check paths.

Check shutdown/backup/crash logic carefully.

Check that no external Vein files are touched.

7. Reporting Issues
When you open an issue, please include:

Windows version

Python version

The steps you ran (batch or Python command)

Relevant snippets from:

Logs/

Runtime/ state JSONs (if applicable)

Whether the server was running/starting/shutting down when the problem occurred

8. License
The project’s final license is still being chosen.
Until then, please treat the code as “all rights reserved” and discuss any redistribution in issues/PRs.

Thanks for contributing to the Vein Server Management Suite!

yaml
Copy code

---

## 4. Codex “bootstrap” message for VS Code

When you open this repo in VS Code and start a Codex chat, you can paste this as your **first message**:

```text
We are working in the VeinServerManagement repository.

Please:
1. Read README.md
2. Read AGENTS.md
3. Skim Docs/control_layer_overview.md and Docs/Developer_Guide.md

Then:
- Summarize the architecture in 5–8 bullet points, focusing on the Controller/ and Controller/Tools/ modules.
- Confirm you understand that Config/config.yaml is the primary config and that shutdown_server.py + utils.py implement the safe shutdown pipeline.

Do not modify any files yet. Wait for my next instruction.