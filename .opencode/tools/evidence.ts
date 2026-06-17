import { tool } from "@opencode-ai/plugin"
import path from "path"
import { runProductTestPython } from "../lib/product_test_runtime"

async function activeEvidence(context: { worktree: string; agent?: string }) {
  const stateText = await runProductTestPython(context, "sandbox_manager.py", ["status"])
  const state = JSON.parse(stateText)
  if (typeof state.run_id !== "string" || state.run_id.length === 0) {
    throw new Error("active sandbox state does not contain a valid run_id")
  }
  return {
    runId: state.run_id as string,
    evidenceDir: path.join(context.worktree, ".test-evidence", state.run_id as string),
  }
}

export const record = tool({
  description: "Validate and append one structured product-test result to the active evidence package",
  args: {
    record: tool.schema.record(tool.schema.string(), tool.schema.any()),
  },
  async execute(args, context) {
    const active = await activeEvidence(context)
    return runProductTestPython(context, "evidence.py", [
      "record",
      "--evidence-dir", active.evidenceDir,
      "--expected-run-id", active.runId,
      "--record-json", JSON.stringify(args.record),
    ])
  },
})

export const write_report = tool({
  description: "Atomically write the final evidence-backed Markdown report to the active evidence directory",
  args: {
    content: tool.schema.string().min(1),
  },
  async execute(args, context) {
    const active = await activeEvidence(context)
    return runProductTestPython(
      context,
      "evidence.py",
      [
        "write-report",
        "--evidence-dir", active.evidenceDir,
        "--expected-run-id", active.runId,
      ],
      { stdinText: args.content },
    )
  },
})

export const finalize = tool({
  description: "Create the final SHA-256 manifest for the active evidence package after all report and patch files exist",
  args: {},
  async execute(_args, context) {
    const active = await activeEvidence(context)
    return runProductTestPython(context, "evidence.py", [
      "finalize",
      "--evidence-dir", active.evidenceDir,
      "--expected-run-id", active.runId,
    ])
  },
})

export const verify = tool({
  description: "Verify the active evidence package against its final SHA-256 manifest",
  args: {},
  async execute(_args, context) {
    const active = await activeEvidence(context)
    return runProductTestPython(context, "evidence.py", [
      "verify",
      "--evidence-dir", active.evidenceDir,
      "--expected-run-id", active.runId,
    ])
  },
})
