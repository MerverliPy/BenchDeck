# Runner setup reference — Phase 1 — WSL2 host tuning

> Agent context note: this is detailed reference material split out of `docs/runner-setup.md` during Cycle 7A. For routine agent context, start with `docs/context-handoffs/runner-setup-summary.md` and open this shard only when the specific phase is relevant.

# Phase 1 — WSL2 host tuning

**Marker**: `<!-- phase-1: done -->` (flip to `<!-- phase-1: done -->`)

Caps WSL2 to 32 GB so Windows has headroom. Adds vhdx initial-size so the disk doesn't bloat silently.

### Step 1.1 — Edit `C:\Users\<you>\.wslconfig`

<!-- step-1.1: done -->

From **Windows PowerShell** (not WSL2 — this is a Windows file):
```powershell
notepad "$env:USERPROFILE\.wslconfig"
```

Paste (adjust `<you>`):
```ini
[wsl2]
memory=32GB
processors=8
swap=8GB
swapFile=D:\\wsl-swap.vhdx
autoMemoryReclaim=gradual
guiApplications=false
localhostForwarding=true
```

Save, close.

**Why**:
- `memory=32GB` — hard cap; leaves 16 GB for Windows on a 48 GB box
- `processors=8` — full i7 core count for WSL2
- `swap=8GB` — fallback if a sandbox needs more than its 4 GB cap transiently
- `autoMemoryReclaim=gradual` — reclaims cached memory back to Windows when idle
- `localhostForwarding=true` — needed for the GitHub runner to reach WSL2-side services

**Verify**: mark `<!-- step-1.1: done -->`.

### Step 1.2 — Restart WSL2 to apply

<!-- step-1.2: done -->

From **Windows PowerShell**:
```powershell
wsl --shutdown
# wait ~5 seconds
wsl -d Ubuntu -e bash -c 'free -h | head -2'
```

**Expected**: `Mem:` row shows total ≤ 32 GB.

**Verify**: mark `<!-- step-1.2: done -->`.

### Step 1.2a — Safety note: never `wsl --shutdown` from inside WSL2

<!-- step-1.2a: done -->

> **Never run `wsl --shutdown` from inside a WSL2 distro.** It creates a circular
> shutdown — the WSL2 init cannot tear down a process that is mid-call into the
> WSL2 control plane — and leaves the LxssManager Windows service in a confused
> state. PowerShell invocations from inside WSL2 may then return
> `Invalid argument` or hang.
>
> Always restart WSL2 from **Windows PowerShell** (or `cmd.exe`):
> ```powershell
> wsl --shutdown
> wsl -d Ubuntu
> ```
> Or, to terminate a single distro without disturbing others:
> ```powershell
> wsl.exe --terminate Ubuntu
> ```
> This rule applies to *any* `wsl.exe` invocation that targets the WSL2 service
> itself (e.g., `--shutdown`, `--status`, `--list`). It does **not** apply to
> `docker`/`dockerd`/regular Linux commands.
>
> This safety note is a documented deviation, also recorded in Appendix B.

---
