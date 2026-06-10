# Project Skills

## /spec-start <task-name>

Start tracking a new task. Creates `specs/active/<task-name>.md` with a template.

Usage: `/spec-start paradigm-city-pages`

Template:
```markdown
# <Task Name>
Started: <date>

## Goal
<What we're trying to accomplish>

## Context
<Relevant background, customer info, constraints>

## Decisions
<Key decisions made during the task>

## Implementation
<What was built/changed>

## Status
- [ ] In progress
```

## /spec-done <category>

Mark the active task as complete and move the spec to the appropriate category.

Usage: `/spec-done customers` or `/spec-done content-system`

Moves `specs/active/<file>.md` → `specs/<category>/<file>.md`

Valid categories: `content-system`, `customers`, `platform`, `pricing`
