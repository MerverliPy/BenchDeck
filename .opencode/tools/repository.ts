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


export const state = tool({
  description: "Read fixed Git repository identity and dirty-state metadata without accepting arbitrary host commands",
  args: {},
  async execute(_args, context) {
    return runPython(context, "sandbox_manager.py", ["repo-state"])
  },
})
