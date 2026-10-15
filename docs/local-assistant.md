# Local assistant implementation

The first assistant is an optional, read-only part of each signed-in member's
workspace. It uses the existing task and calendar services to collect records
that member can see. Each member chooses whether tasks and calendar events may
be included. The question and selected records go to a model server bound to a
literal loopback address on the same computer. The app never gives the model SQL,
filesystem, network, or record-editing tools.

The assistant starts disabled for every member. Configuration is saved per
profile in the local configuration folder, separate from the household database.
The user can inspect the exact record summaries included with each answer and
disable access again. Answers are suggestions, not a source of truth for dates or
record contents. The app continues to work with no model installed.

This first slice supports the native desktop launch with Ollama or llama.cpp.
Docker Compose keeps its existing `network_mode: none`; an explicit, narrowly
scoped local-model bridge remains separate work. Approved writes, LAN endpoints,
model downloads, and autonomous actions remain outside this read-only slice.
