import { tool } from "@opencode-ai/plugin"
import { runProductTestPython } from "../lib/product_test_runtime"

export const create = tool({
  description: "Create an isolated rootless-Docker BenchDeck test sandbox and optionally install development dependencies through the package allowlist",
  args: {
    pythonVersion: tool.schema.enum(["3.11", "3.12", "3.13"]).default("3.12"),
    installDependencies: tool.schema.boolean().default(true),
    replace: tool.schema.boolean().default(false),
    quick: tool.schema.boolean().default(false).describe("Skip Docker build and dependency install when cached"),
  },
  async execute(args, context) {
    const command = ["create", "--python-version", args.pythonVersion]
    if (args.installDependencies) command.push("--install-dependencies")
    if (args.replace) command.push("--replace")
    if (args.quick) command.push("--quick")
    return runProductTestPython(context, "sandbox_manager.py", command)
  },
})

export const status = tool({
  description: "Return the active BenchDeck product-test sandbox identity, self-test, and container state",
  args: {},
  async execute(_args, context) {
    return runProductTestPython(context, "sandbox_manager.py", ["status"])
  },
})

export const exec = tool({
  description: "Execute a command only inside the active offline disposable BenchDeck sandbox and preserve command evidence",
  args: {
    command: tool.schema.string().min(1).describe("Command executed by bash inside /workspace"),
    cwd: tool.schema.string().default("").describe("Relative directory under /workspace"),
    timeoutSeconds: tool.schema.number().int().min(1).max(3600).default(300),
    evidenceClass: tool.schema.enum([
      "STATIC_EVIDENCE",
      "SIMULATED_REGRESSION_EVIDENCE",
      "LOCAL_BLACK_BOX_EVIDENCE",
      "INDEPENDENT_REPRODUCTION",
    ]).default("LOCAL_BLACK_BOX_EVIDENCE"),
  },
  async execute(args, context) {
    return runProductTestPython(context, "sandbox_manager.py", [
      "exec",
      "--command", args.command,
      "--cwd", args.cwd,
      "--timeout", String(args.timeoutSeconds),
      "--evidence-class", args.evidenceClass,
    ])
  },
})

export const exec_with_output = tool({
  description: "Execute a command inside the sandbox and retrieve matching output files",
  args: {
    command: tool.schema.string().min(1).describe("Command to execute inside /workspace"),
    cwd: tool.schema.string().default("").describe("Relative directory under /workspace"),
    timeoutSeconds: tool.schema.number().int().min(1).max(3600).default(300),
    captureGlob: tool.schema.string().default("").describe("Glob pattern for files to retrieve (e.g. '*.json', '*.md')"),
    evidenceClass: tool.schema.enum([
      "STATIC_EVIDENCE",
      "SIMULATED_REGRESSION_EVIDENCE",
      "LOCAL_BLACK_BOX_EVIDENCE",
      "INDEPENDENT_REPRODUCTION",
    ]).default("LOCAL_BLACK_BOX_EVIDENCE"),
  },
  async execute(args, context) {
    const cmd = [
      "exec-output",
      "--command", args.command,
      "--cwd", args.cwd,
      "--timeout", String(args.timeoutSeconds),
      "--evidence-class", args.evidenceClass,
    ]
    if (args.captureGlob) cmd.push("--capture-glob", args.captureGlob)
    return runProductTestPython(context, "sandbox_manager.py", cmd)
  },
})

export const export_patch = tool({
  description: "Export all candidate sandbox changes as a binary-capable Git patch under the evidence directory",
  args: {},
  async execute(_args, context) {
    return runProductTestPython(context, "sandbox_manager.py", ["patch"])
  },
})

export const destroy = tool({
  description: "Destroy active product-test containers and network while preserving evidence; optionally purge the disposable workspace",
  args: {
    purgeWorkspace: tool.schema.boolean().default(false),
  },
  async execute(args, context) {
    const command = ["destroy"]
    if (args.purgeWorkspace) command.push("--purge")
    return runProductTestPython(context, "sandbox_manager.py", command)
  },
})
