/**
 * The shell command guard, applied to pi's `bash` tool.
 *
 * The rules live in one script, dots/claude/hooks/pretooluse-bash.py, which
 * Claude Code and Codex run as a hook. This handler gives it the same payload
 * and reads the same answer, so a rule added there applies here without a
 * change. There is no sandbox and no approval prompt: a command is either
 * run or refused with the script's reason.
 *
 * A guard that cannot run refuses the command, because a silent pass would
 * look the same as an allowed command.
 */

import { spawn } from "node:child_process";
import { realpathSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { type ExtensionAPI, isToolCallEventType } from "@earendil-works/pi-coding-agent";

const GUARD_TIMEOUT_MS = 3000;

/** The guard script beside this package in the dots tree, through any symlink. */
export function guardScriptPath(): string {
	const here = dirname(realpathSync(fileURLToPath(import.meta.url)));
	return resolve(here, "../../claude/hooks/pretooluse-bash.py");
}

/** Returns the refusal reason, or undefined when the command may run. */
export function checkCommand(command: string, cwd: string, script = guardScriptPath()): Promise<string | undefined> {
	const payload = JSON.stringify({ tool_name: "Bash", tool_input: { command }, cwd });
	return new Promise((settle) => {
		const refuse = (problem: string) => settle(`The command guard could not run (${problem}); refusing the command.`);
		const child = spawn(script, ["pi"], { stdio: ["pipe", "pipe", "pipe"], timeout: GUARD_TIMEOUT_MS });
		let stdout = "";
		let stderr = "";
		child.stdout.on("data", (chunk) => (stdout += chunk));
		child.stderr.on("data", (chunk) => (stderr += chunk));
		child.on("error", (error) => refuse(error.message));
		child.on("close", (code, signal) => {
			if (signal) return refuse(`stopped by ${signal}`);
			if (code !== 0) return refuse(`exit ${code}: ${stderr.trim().slice(0, 200)}`);
			if (!stdout.trim()) return settle(undefined);
			try {
				const decision = JSON.parse(stdout).hookSpecificOutput ?? {};
				settle(decision.permissionDecision === "deny" ? String(decision.permissionDecisionReason) : undefined);
			} catch {
				refuse("unreadable answer");
			}
		});
		child.stdin.on("error", () => {});
		child.stdin.end(payload);
	});
}

export default function guard(pi: ExtensionAPI) {
	pi.on("tool_call", async (event, ctx) => {
		if (!isToolCallEventType("bash", event)) return;
		const reason = await checkCommand(event.input.command, ctx.cwd);
		if (reason) return { block: true, reason };
	});
}
