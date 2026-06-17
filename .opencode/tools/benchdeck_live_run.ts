import { tool } from "@opencode-ai/plugin"
import { runProductTestPython } from "../lib/product_test_runtime"

export default tool({
  description: "Run a real BenchDeck OpenAI benchmark in a dedicated ephemeral container with a mounted test key, api.openai.com-only egress, and strict budgets",
  args: {
    agentA: tool.schema.string().min(1).describe("Relative path to the first test agent Markdown file"),
    agentB: tool.schema.string().default(""),
    plan: tool.schema.string().default("").describe("Optional relative path to a small frozen plan"),
    model: tool.schema.string().default("gpt-4o-mini"),
    plannerModel: tool.schema.string().default("gpt-4o-mini"),
    judgeModel: tool.schema.string().default("gpt-4o-mini"),
    judges: tool.schema.number().int().min(1).max(3).default(1),
    timeoutSeconds: tool.schema.number().int().min(10).max(300).default(90),
    maxRetries: tool.schema.number().int().min(1).max(5).default(3),
    maxLogicalRequests: tool.schema.number().int().min(1).max(100).default(30),
    maxHttpAttempts: tool.schema.number().int().min(1).max(150).default(45),
    maxTotalInputTokens: tool.schema.number().int().min(1000).max(1000000).default(120000),
    maxTotalOutputTokens: tool.schema.number().int().min(1000).max(250000).default(30000),
    maxOutputTokensPlanner: tool.schema.number().int().min(100).max(20000).default(4000),
    maxOutputTokensAgent: tool.schema.number().int().min(100).max(20000).default(4000),
    maxOutputTokensJudge: tool.schema.number().int().min(100).max(20000).default(4000),
  },
  async execute(args, context) {
    return runProductTestPython(context, "live_benchdeck_run.py", [
      "--agent-a", args.agentA,
      "--agent-b", args.agentB,
      "--plan", args.plan,
      "--model", args.model,
      "--planner-model", args.plannerModel,
      "--judge-model", args.judgeModel,
      "--judges", String(args.judges),
      "--timeout", String(args.timeoutSeconds),
      "--max-retries", String(args.maxRetries),
      "--max-logical-requests", String(args.maxLogicalRequests),
      "--max-http-attempts", String(args.maxHttpAttempts),
      "--max-total-input-tokens", String(args.maxTotalInputTokens),
      "--max-total-output-tokens", String(args.maxTotalOutputTokens),
      "--max-output-tokens-planner", String(args.maxOutputTokensPlanner),
      "--max-output-tokens-agent", String(args.maxOutputTokensAgent),
      "--max-output-tokens-judge", String(args.maxOutputTokensJudge),
    ], { live: true })
  },
})
