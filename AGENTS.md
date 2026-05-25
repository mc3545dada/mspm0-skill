# Repository Agent Instructions

This repository packages an installable MSPM0 CCS skill.

The installable skill lives at:

```text
skills/mspm0-ccs/
```

Root-level `AGENTS.md` and `CLAUDE.md` are for agents developing this repository. They are not the user-facing installation entrypoint.

This file is the canonical source for repository-development agent rules. Claude Code should load this file through `CLAUDE.md`.

## Repository Rules

- Keep the installable skill self-contained under `skills/mspm0-ccs/`.
- The skill entrypoint is `skills/mspm0-ccs/SKILL.md`.
- Put long reference docs in `skills/mspm0-ccs/references/`.
- Put executable helper scripts in `skills/mspm0-ccs/scripts/`.
- Put reusable snippets in `skills/mspm0-ccs/assets/snippets/`.
- Put compact example packages in `skills/mspm0-ccs/examples/`; each should prefer `example.syscfg`, `manifest.json`, `README.md`, and `src/`.
- Do not reintroduce root-level `docs/`, `tools/`, `snippets/`, or `examples/` as the primary structure.
- Do not reintroduce root-level `SKILL.md`; the installable skill entrypoint is inside `skills/mspm0-ccs/`.

## Validation

After changing scripts, run:

```text
python -m py_compile skills/mspm0-ccs/scripts/check_syscfg.py skills/mspm0-ccs/scripts/serial_console.py skills/mspm0-ccs/scripts/index_syscfg_examples.py skills/mspm0-ccs/scripts/list_examples.py skills/mspm0-ccs/scripts/capture_example.py skills/mspm0-ccs/scripts/ccs_dss_debug.py
```

After changing references or examples, run the checker against the repository to catch obvious path or SysConfig issues:

```text
python skills/mspm0-ccs/scripts/check_syscfg.py .
```

Expected warnings are acceptable because the examples are compact reference packages, not complete CCS projects.

## Documentation

When updating installation or usage instructions, update the root `README.md`.

When updating actual Agent behavior, update `skills/mspm0-ccs/SKILL.md` and the relevant file under `skills/mspm0-ccs/references/`.
