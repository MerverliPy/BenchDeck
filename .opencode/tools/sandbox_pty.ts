import { tool } from "@opencode-ai/plugin"
import path from "path"

function assertProductTestAgent(context: { agent?: string }): void {
  const agent = context.agent ?? ""
  if (agent !== "benchdeck-product-tester" && !agent.startsWith("benchdeck-test-")) {
    throw new Error(`tool is restricted to BenchDeck product-test agents; caller=${agent || "unknown"}`)
  }
}

async function runPython(
  context: { worktree: string; agent?: string },
  scriptName: string,
  args: string[],
): Promise<string> {
  assertProductTestAgent(context)
  const script = path.join(context.worktree, ".product-test", "scripts", scriptName)
  const proc = Bun.spawn(["python3", script, ...args], {
    cwd: context.worktree,
    stdout: "pipe",
    stderr: "pipe",
    env: process.env,
  })
  const [stdout, stderr, code] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
    proc.exited,
  ])
  if (code !== 0) {
    throw new Error((stderr || stdout || `tool exited ${code}`).trim())
  }
  return stdout.trim()
}


export default tool({
  description: "Run a real command under a PTY inside the offline BenchDeck sandbox, send terminal actions, normalize frames, and preserve raw evidence",
  args: {
    command: tool.schema.string().min(1),
    rows: tool.schema.number().int().min(5).max(200).default(24),
    cols: tool.schema.number().int().min(10).max(400).default(80),
    term: tool.schema.string().default("xterm-256color"),
    actions: tool.schema.array(
      tool.schema.object({
        type: tool.schema.enum(["sleep", "send", "key", "resize", "signal", "expect"]),
        label: tool.schema.string().optional(),
        text: tool.schema.string().optional(),
        key: tool.schema.string().optional(),
        seconds: tool.schema.number().optional(),
        rows: tool.schema.number().int().optional(),
        cols: tool.schema.number().int().optional(),
        signal: tool.schema.string().optional(),
        contains: tool.schema.string().optional(),
        timeout: tool.schema.number().optional(),
      }),
    ).default([]),
  },
  async execute(args, context) {
    return runPython(context, "pty_runner.py", [
      "--command", args.command,
      "--rows", String(args.rows),
      "--cols", String(args.cols),
      "--term", args.term,
      "--actions-json", JSON.stringify(args.actions),
    ])
  },
})
