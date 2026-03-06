# Framework Docs: Industry Patterns

## E2B (Code Interpreter SDK)

### Architecture
- Firecracker microVMs for isolation
- REST API + Python/JS SDKs
- Sandboxes have configurable timeouts (default 5 min, max 24h)
- Custom templates from Dockerfiles
- Native file I/O (not shell-based)

### Protocol Surface
```
create(template?) -> sandbox_id
commands.run(cmd, timeout?, cwd?, envs?) -> {exit_code, stdout, stderr}
files.read(path) -> content
files.write(path, content) -> void
files.list(path) -> entries
close() -> void
```

## SWE-agent / SWE-ReX

### Architecture
- Agent runs outside sandbox (control plane)
- SWE-ReX runtime abstraction with swappable backends (Docker, Modal, Fargate)
- Single `execute(command)` primitive
- File operations via shell commands (`cat`, `echo`, etc.)

### Protocol Surface
```
start(config) -> runtime
execute(command, timeout?) -> {stdout, stderr, exit_code}
read_file(path) -> content  # via cat
write_file(path, content) -> void  # via echo/tee
close() -> void
```

## OpenHands (formerly OpenDevin)

### Architecture
- Action/Observation type system
- Each operation is a typed Action with a corresponding Observation
- Event stream architecture
- Docker + E2B backends

### Protocol Surface
```
CmdRunAction(command, timeout?) -> CmdOutputObservation(exit_code, stdout, stderr)
FileReadAction(path) -> FileReadObservation(content)
FileWriteAction(path, content) -> FileWriteObservation(success)
BrowseURLAction(url) -> BrowseObservation(content)
```

## LangChain DeepAgents

### Architecture
- `BaseSandbox` abstract class (not Protocol)
- Single `execute(command)` method
- Concrete implementations: ModalSandbox, DaytonaSandbox, RunloopSandbox
- File I/O derived from `execute()` in base class

### Protocol Surface
```
create() -> sandbox
execute(command) -> {stdout, stderr, exit_code}
read_file(path) -> str  # calls execute("cat path")
write_file(path, content) -> void  # calls execute("echo content > path")
close() -> void
```

## Codex CLI (OpenAI)

### Architecture
- OS-level sandboxing (Seatbelt on macOS, Landlock on Linux)
- No container overhead
- Network disabled by default
- Filesystem restricted to project directory
- Single-user local tool only

## Vercel AI SDK Sandbox

### Architecture
- Firecracker-based (via E2B partnership)
- `createSandbox()` / `sandbox.exec()` / `sandbox.readFile()` / `sandbox.writeFile()`
- Tight integration with Next.js

## Common Patterns Across All Systems

| Feature | E2B | SWE-ReX | OpenHands | DeepAgents | Codex CLI |
|---------|-----|---------|-----------|------------|-----------|
| execute(cmd) | Yes | Yes | Yes | Yes | Yes |
| File I/O (native) | Yes | No | Yes | No | N/A |
| File I/O (shell) | Also | Yes | Also | Yes | N/A |
| Async context mgr | Yes | Yes | Yes | Yes | No |
| Multiple backends | Yes* | Yes | Yes | Yes | No |
| Timeout support | Yes | Yes | Yes | Yes | Yes |
| Status/health | Yes | No | Yes | No | N/A |

**Universal**: `execute(command)` as core primitive, async lifecycle, timeout support.
**Split**: File I/O as native typed methods (E2B, OpenHands) vs shell-derived (SWE-ReX, DeepAgents).
**Recommendation**: Typed file I/O methods on Protocol, with shell-based fallback in a mixin for backends that lack native support.
