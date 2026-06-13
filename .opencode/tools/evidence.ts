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


export const record = tool({
  description: "Append one structured product-test result to the active evidence package",
  args: {
    record: tool.schema.record(tool.schema.string(), tool.schema.any()),
  },
  async execute(args, context) {
    const stateText = await runPython(context, "sandbox_manager.py", ["status"])
    const state = JSON.parse(stateText)
    const evidenceDir = path.join(context.worktree, ".test-evidence", state.run_id)
    return runPython(context, "evidence.py", [
      "--evidence-dir", evidenceDir,
      "--record-json", JSON.stringify(args.record),
    ])
  },
})

export const write_report = tool({
  description: "Write the final evidence-backed Markdown report to the active product-test evidence directory",
  args: {
    content: tool.schema.string().min(1),
  },
  async execute(args, context) {
    const stateText = await runPython(context, "sandbox_manager.py", ["status"])
    const state = JSON.parse(stateText)
    const reportPath = path.join(context.worktree, ".test-evidence", state.run_id, "FINAL_PRODUCT_TEST_REPORT.md")
    await Bun.write(reportPath, args.content)
    return JSON.stringify({ ok: true, path: reportPath })
  },
})
