# Specs Directory

Specification documents tracking decisions, logic, and implementation details for the PracticeRank platform.

## Structure

```
specs/
├── active/          # Current task context — ONE task at a time
├── content-system/  # Content generation, recommender, blog formatting rules
├── customers/       # Per-customer specs, onboarding decisions, content rules
├── platform/        # Dashboard, DB schema, deployment, infrastructure
├── pricing/         # Service tiers, pricing models, proposals
```

## Workflow

1. When starting a task, create a spec in `specs/active/` (e.g., `specs/active/task-name.md`)
2. Use it to track context, decisions, and progress during the task
3. When done, move the spec to the appropriate category subfolder
4. The spec becomes permanent documentation of what was built and why
