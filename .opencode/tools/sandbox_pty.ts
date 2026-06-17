import { tool } from "@opencode-ai/plugin"
import { runProductTestPython } from "../lib/product_test_runtime"

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
    return runProductTestPython(context, "pty_runner.py", [
      "--command", args.command,
      "--rows", String(args.rows),
      "--cols", String(args.cols),
      "--term", args.term,
      "--actions-json", JSON.stringify(args.actions),
    ])
  },
})
