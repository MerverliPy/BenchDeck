import { tool } from "@opencode-ai/plugin"
import { runProductTestPython } from "../lib/product_test_runtime"

export const state = tool({
  description: "Read fixed Git repository identity and dirty-state metadata without accepting arbitrary host commands",
  args: {},
  async execute(_args, context) {
    return runProductTestPython(context, "sandbox_manager.py", ["repo-state"])
  },
})
