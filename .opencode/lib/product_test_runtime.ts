import path from "path"

export type ProductTestContext = {
  worktree: string
  agent?: string
}

type RunOptions = {
  live?: boolean
  stdinText?: string
}

const PRODUCT_TEST_AGENT = "benchdeck-product-tester"
const PRODUCT_TEST_PREFIX = "benchdeck-test-"

export function assertProductTestAgent(context: { agent?: string }): void {
  const agent = context.agent ?? ""
  if (agent !== PRODUCT_TEST_AGENT && !agent.startsWith(PRODUCT_TEST_PREFIX)) {
    throw new Error(
      `tool is restricted to BenchDeck product-test agents; caller=${agent || "unknown"}`,
    )
  }
}

function redact(text: string): string {
  return text
    .replace(/\bsk-[A-Za-z0-9_-]{10,}\b/g, "[REDACTED_API_KEY]")
    .replace(/(Bearer\s+)[A-Za-z0-9._~+/=-]+/gi, "$1[REDACTED]")
}

function childEnvironment(live: boolean): Record<string, string> {
  const allowed = [
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TMPDIR",
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "XDG_RUNTIME_DIR",
    "DOCKER_HOST",
    "DOCKER_CONTEXT",
    "DOCKER_TLS_VERIFY",
    "DOCKER_CERT_PATH",
    "BENCHDECK_PRODUCT_TEST_RUNTIME",
  ]

  if (live) {
    allowed.push("BENCHDECK_LIVE_ENABLED", "BENCHDECK_TEST_OPENAI_KEY_FILE")
  }

  const env: Record<string, string> = {
    PYTHONDONTWRITEBYTECODE: "1",
    PYTHONNOUSERSITE: "1",
    PYTHONUNBUFFERED: "1",
  }

  for (const name of allowed) {
    const value = process.env[name]
    if (value !== undefined) env[name] = value
  }
  return env
}

export async function runProductTestPython(
  context: ProductTestContext,
  scriptName: string,
  args: string[],
  options: RunOptions = {},
): Promise<string> {
  assertProductTestAgent(context)

  if (!/^[A-Za-z0-9_.-]+\.py$/.test(scriptName)) {
    throw new Error(`invalid product-test script name: ${scriptName}`)
  }

  const scriptRoot = path.resolve(context.worktree, ".product-test", "scripts")
  const script = path.resolve(scriptRoot, scriptName)
  if (!script.startsWith(`${scriptRoot}${path.sep}`)) {
    throw new Error(`product-test script escapes the approved directory: ${scriptName}`)
  }

  const proc = Bun.spawn(["python3", script, ...args], {
    cwd: context.worktree,
    stdout: "pipe",
    stderr: "pipe",
    stdin: options.stdinText === undefined ? "ignore" : "pipe",
    env: childEnvironment(Boolean(options.live)),
  })

  if (options.stdinText !== undefined) {
    proc.stdin.write(options.stdinText)
    proc.stdin.end()
  }

  const [stdout, stderr, code] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
    proc.exited,
  ])

  if (code !== 0) {
    throw new Error(redact(stderr || stdout || `tool exited ${code}`).trim())
  }
  return redact(stdout).trim()
}
