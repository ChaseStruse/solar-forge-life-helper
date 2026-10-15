# Local model contract

The live instructions sent to a local model are defined in
[`assistant_guidance.py`](../src/solar_forge_desktop/assistant_guidance.py). This page
explains those instructions for maintainers and model evaluators. Changing this page
alone does not change model behavior; update the runtime instructions and tests too.

## What the model receives

Each request has a system instruction and a JSON user payload with `today`,
`upcoming_window`, `member_request`, `enabled_categories`, and `selected_records`.
The app sends only categories enabled by the signed-in member. The default context
has up to 30 due or overdue open tasks due by the end of the next 14 days, 10 open
undated tasks, and 40 calendar occurrences in that window. If the request names a
task or event, the app may add up to eight title matches from the authorized data,
including records outside that window. A task ID mentioned in the request can also
bring that visible open task into context. Task summaries show the ID, title, owner
ID, due time, visibility, and whether this member can edit the task. Event summaries
show the ID, title, owner ID, local start and end, and visibility; a retrieved
recurring event shows its next occurrence within a year and repeat pattern.

This context is bounded. The model must not treat the absence of a record as proof
that none exists. It must not obey instructions embedded in record titles or invent
an ID, date, time, owner, or action result. `today` resolves relative dates. Stored
times are local wall-clock values, so the model should not silently add a time zone.

## Questions

The question path is read-only. It answers from the supplied summaries, cites the
relevant names and dates in plain language, and asks for missing details when the
context cannot support an answer. The model has no database, filesystem, calendar,
task, reminder, or network tool. Its answer never confirms a record change.

## Change drafts

The model returns exactly one JSON object. The application accepts these forms:

| Operation | Exact fields | Effect after approval |
| --- | --- | --- |
| `create_task` | `operation`, `title`, `due_at`, `visibility` | Create a task owned by the signed-in member. |
| `update_task` | `operation`, `task_id`, `title`, `due_at` | Replace the title and due time of one of that member's open tasks. |
| `create_event` | `operation`, `title`, `category`, `starts_at`, `ends_at`, `visibility` | Create one timed, nonrecurring event owned by the signed-in member. |

`due_at` is `null` or `YYYY-MM-DDTHH:MM`. Event start and end use the same minute
format, and end must follow start. Visibility is `private` unless the member
explicitly requests household sharing. For an event without a stated category, the
model uses `Personal` for private or `Home` for household. An update must copy any unchanged title or
due value from the selected task summary; it cannot change ownership, sharing,
completion, or reminders. The model should return
`{"clarification":"What time should the event start?"}` when a required detail is
missing or the request asks for multiple or unsupported changes.

For example, given `today: 2026-10-14`, “Add a private task to buy milk tomorrow
at 18:00” should yield:

```json
{"operation":"create_task","title":"Buy milk","due_at":"2026-10-15T18:00","visibility":"private"}
```

Given `Task #42: Call dentist | owner: #7 | editable: yes | due:
2026-10-20T09:00 | private`, “Move my dentist task to October 22 at 10:30” should
yield:

```json
{"operation":"update_task","task_id":42,"title":"Call dentist","due_at":"2026-10-22T10:30"}
```

The app rejects malformed output, extra or repeated fields, nonexistent or
unauthorized task IDs, and operations for disabled categories. A draft changes no
data. The member sees the exact fields and explicitly approves or cancels. At
approval the app checks permissions and task freshness again, then calls the same
validated task or calendar service used by the rest of the UI. Each approval or
rejection is logged locally for that member. The model receives no execution tool
and cannot approve its own proposal.
