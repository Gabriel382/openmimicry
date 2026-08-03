# Local agents and project folders

OpenMimicry v1.8 can delegate work without making the foreground conversation
wait. Project roots tell a local agent which repository or folder the user
means; task history and completion notifications are stored in the local task
journal.

## Claude subscription mode

Install and authenticate Claude Code normally, then confirm:

```bash
claude --version
claude
```

The integrated profile uses `auth_mode: subscription`. OpenMimicry does not
forward `ANTHROPIC_API_KEY` in this mode and does not bypass Claude's permission
system.

```yaml
tasks:
  default_runtime: claude_code
  database_path: ~/.openmimicry/tasks/tasks.sqlite3
  runtimes:
    claude_code:
      adapter: claude_code
      cli: claude
      auth_mode: subscription
      working_dir: .
```

For API billing instead, set `auth_mode: api` and provide
`ANTHROPIC_API_KEY` outside YAML.

## PicoClaw

PicoClaw is a separate optional MIT executable. After installing and
configuring it, verify:

```bash
picoclaw status
picoclaw agent -m "Reply with OK"
```

Configure:

```yaml
tasks:
  runtimes:
    picoclaw:
      adapter: picoclaw
      cli: picoclaw
      working_dir: .
```

OpenMimicry does not copy PicoClaw provider keys, MCP settings, or security
files.

## Register a project

The local API is intentionally small:

```bash
curl -X POST http://127.0.0.1:8000/tasks/projects \
  -H "Content-Type: application/json" \
  -d '{"name":"OpenMimicry","root_path":"/absolute/path/openmimicry","provider_runtime":"claude_code"}'
```

On Windows use an escaped absolute path in JSON, for example
`C:\\Users\\me\\Documents\\openmimicry`.

Submit a background task:

```bash
curl -X POST http://127.0.0.1:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"summary":"Run tests","instructions":"Run the relevant tests and explain failures.","project_id":"PROJECT_ID","preferred_runtime":"claude_code","capabilities":["code"]}'
```

Inspect:

- `GET /tasks` — durable task list;
- `GET /tasks/{id}` — request, result, and event timeline;
- `GET /tasks/projects` — registered project roots;
- `GET /tasks/notifications` — queued completions;
- `POST /tasks/notifications/{id}/read` — acknowledge without disrupting chat.

The dashboard shows the task journal and notification center. Closing the
desktop does not erase terminal history. Work that was live when the backend
stopped is marked interrupted on the next startup.

## Project selection policy

OpenMimicry never guesses a writeable project root from arbitrary conversation.
A task should include a registered `project_id`, or a deliberately configured
runtime working directory. Relative paths are resolved by the selected agent
inside that root. Provider session ids are metadata, never project identity.

