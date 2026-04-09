# GitHub Project Standard

## Purpose

Define the required standard for the GitHub Project used by this repository.

## Rule

During initialization, the GitHub Project linked to the repository must be created or configured strictly according to this standard.

## Required properties

- The project must exist
- The project must be linked to the repository
- The project must be configured for the workflow used by this template
- The project workflow board must be driven by the project `Status` field
- The number of board columns must equal the number of workflow statuses
- Moving a task through the workflow must update the project `Status` field to the same value
- GitHub Project `Status` is the only canonical source of workflow status
- The canonical workflow statuses are `ready`, `in_progress`, `review`, `in_testing`, and `done`
- issue body is not a status carrier

## Project Status field

The GitHub Project must use the built-in `Status` single-select field as the canonical Kanban field.

Required rule:

- the `Status` field options must exactly match `ready`, `in_progress`, `review`, `in_testing`, and `done`
- the board layout must group items by the `Status` field
- each `Status` option must map to exactly one Kanban column

Required workflow statuses:

- name: `ready` | color: `0052CC` | description: `Task is prepared for execution and may be selected by the issue-driven workflow.`
- name: `in_progress` | color: `FBCA04` | description: `Task is currently being executed by the assigned role.`
- name: `review` | color: `A371F7` | description: `Task has been implemented and is waiting for review before verification.`
- name: `in_testing` | color: `1D76DB` | description: `Task has been implemented and is under verification before completion.`
- name: `done` | color: `0E8A16` | description: `Task is completed and no longer selectable for execution.`

## Labels

The project must contain the complete required set of labels used by the workflow.

Required label groups:

- role labels
- priority labels

The agent must not invent missing labels, substitute labels, or infer label values from context.
The list of labels to create is given below.

### Role labels

- `role:business-analyst` | color: `1D76DB` | description: `Responsible for business analysis artifacts and business task framing.`
- `role:system-analyst` | color: `0E8A16` | description: `Responsible for system analysis artifacts, system behavior, and formal contracts.`
- `role:architect` | color: `5319E7` | description: `Responsible for architecture decisions, structural models, and cross-cutting technical constraints.`
- `role:frontend-developer` | color: `FBCA04` | description: `Responsible for frontend implementation tasks and related delivery changes.`
- `role:backend-developer` | color: `B60205` | description: `Responsible for backend implementation tasks and related delivery changes.`
- `role:devops` | color: `0052CC` | description: `Responsible for infrastructure, delivery pipeline, and operational environment changes.`

### Priority labels

- `priority:critical` | color: `B60205` | description: `Immediate action required because the workflow or delivery is at risk.`
- `priority:high` | color: `D93F0B` | description: `High execution priority with strong delivery impact.`
- `priority:medium` | color: `FBCA04` | description: `Normal planned priority for regular execution flow.`
- `priority:low` | color: `0E8A16` | description: `Lower urgency task that can wait behind higher-priority work.`
