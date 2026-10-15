# Local assistant

The assistant is an optional part of each signed-in member's
workspace. It uses the existing task and calendar services to collect records
that member can see. Each member chooses whether tasks and calendar events may
be included. The question and selected records go to a model server bound to a
literal loopback address on the same computer. The app never gives the model SQL,
filesystem, network, or direct record-editing tools.

To use it, start Ollama or llama.cpp locally, install a chat-capable model there,
then open **Local Assistant** in the sidebar. Choose the server and model, use
**Test connection and list models**, select the categories to include, and press
**Save and enable**. The initial context contains at most 30 dated open tasks due
within 14 days, 10 open tasks without a due date, and 40 calendar occurrences in
the same 14-day window. Only tasks and events visible to the signed-in member are
eligible. A request sends the question and those record summaries to the selected
model; the summaries appear below the answer. The connection test sends no records.
Choose **Disable assistant** to stop future requests. A request already in flight
may have reached the model before the disable action.

For a change, enter one request in **Request one change** and select **Draft
change for review**. The assistant can propose creating a task, changing the
title or due date of one of your open tasks, or creating a simple timed calendar
event. It cannot update another member's task, edit existing events, delete
records, set reminders, or make recurring events. The preview lists the exact
owner, visibility, and fields. Check it carefully, then select **Approve this
change** or **Cancel proposal**. Drafting alone does not save anything. A new
draft replaces and rejects the previous draft; a proposal can be handled only
once. If the referenced task changed since the preview, approval fails and you
must request a new draft. Approved and rejected decisions appear in the local
action history, saved privately for that member in the configuration folder.

The assistant starts disabled for every member. Configuration is saved per
profile in the local configuration folder, separate from the household database.
The user can inspect the exact record summaries included with each answer and
disable access again. Answers are suggestions, not a source of truth for dates or
record contents. The app continues to work with no model installed.

The endpoint restriction applies to the app's HTTP connection. Configure the
model server itself for local-only operation and choose a locally installed model;
the app cannot verify whether a separate model server relays requests elsewhere.
Local model responses can be inaccurate and should be checked against the shown
records.

This assistant supports the native desktop launch with Ollama or llama.cpp.
Docker Compose keeps its existing `network_mode: none`; an explicit, narrowly
scoped local-model bridge remains separate work. LAN endpoints, model downloads,
and autonomous actions remain outside the current implementation.
