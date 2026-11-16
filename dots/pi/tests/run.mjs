// Exercises the extensions against a stand-in for pi's extension API.
//
// Run from a directory where `node_modules` resolves pi's own packages
// (flake/tests/pi.nix arranges that) with:
//   SINNIX_RANK_ARGV  the ranking command, as a JSON array of words
//   SINNIX_RANK_ROOT  a scratch ranking root
//   PI_CODING_AGENT_DIR  a scratch agent directory
// `--schemas` prints the registered tools' schemas and the presets instead.

import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import ask from "../extensions/ask.ts";
import compare, { actionForKey, sideBySide } from "../extensions/compare.ts";
import guard, { checkCommand } from "../extensions/guard.ts";
import planBilling, { chargedToUsageCredits } from "../extensions/plan-billing.ts";
import presets, { loadPresets } from "../extensions/presets.ts";
import { describeItem, fileDisplay } from "../lib/item-display.ts";
import { RankEngine, Sitting } from "../lib/rank.ts";

const rankArgv = JSON.parse(process.env.SINNIX_RANK_ARGV ?? '["sinnix-rank"]');
const agentDir = process.env.PI_CODING_AGENT_DIR;

function exec(command, args) {
	const argv = command === "sinnix-rank" ? [...rankArgv, ...args] : [command, ...args];
	return new Promise((settle) =>
		execFile(argv[0], argv.slice(1), (error, stdout, stderr) =>
			settle({ stdout, stderr, code: error ? (typeof error.code === "number" ? error.code : 1) : 0 }),
		),
	);
}

/** A stand-in for pi: records what extensions register and lets tests fire events. */
function fakePi(flagValues = {}) {
	const builtin = ["read", "bash", "edit", "write", "grep", "find", "ls", "tool_search"];
	const state = {
		tools: new Map(),
		commands: new Map(),
		handlers: new Map(),
		flags: new Map(),
		entries: [],
		active: ["read", "bash", "edit", "write"],
		thinking: "medium",
	};
	const pi = {
		on: (event, handler) => state.handlers.set(event, [...(state.handlers.get(event) ?? []), handler]),
		registerTool: (tool) => state.tools.set(tool.name, tool),
		registerCommand: (name, options) => state.commands.set(name, options),
		registerFlag: (name, options) => state.flags.set(name, options),
		getFlag: (name) => flagValues[name],
		getAllTools: () => [...builtin, ...state.tools.keys()].map((name) => ({ name })),
		getActiveTools: () => [...state.active],
		setActiveTools: (names) => (state.active = [...names]),
		getThinkingLevel: () => state.thinking,
		setThinkingLevel: (level) => (state.thinking = level),
		setModel: async () => true,
		appendEntry: (customType, data) => state.entries.push({ type: "custom", customType, data }),
		exec,
	};
	const fire = async (event, payload, ctx) => {
		let last;
		for (const handler of state.handlers.get(event) ?? []) last = (await handler(payload, ctx)) ?? last;
		return last;
	};
	return { pi, state, fire };
}

/** A front end that answers dialogs from a script, the way an RPC client would. */
function fakeContext(state, answers = [], overrides = {}) {
	const seen = { selects: [], notes: [], status: {} };
	const ctx = {
		mode: "rpc",
		hasUI: true,
		cwd: process.cwd(),
		model: undefined,
		modelRegistry: { find: () => undefined },
		sessionManager: { getEntries: () => state.entries },
		abort: () => (seen.aborted = true),
		ui: {
			select: async (title, options) => {
				seen.selects.push({ title, options });
				const answer = answers.shift();
				return typeof answer === "function" ? answer(options) : answer;
			},
			input: async () => answers.shift(),
			notify: (message, type) => seen.notes.push({ message, type }),
			setStatus: (key, value) => (seen.status[key] = value),
		},
		...overrides,
	};
	return { ctx, seen };
}

const tests = [];
const test = (name, body) => tests.push([name, body]);

// Assembled so this file does not itself read as the command it tests.
const forcePush = ["git", "push", "--force", "origin", "master"].join(" ");
const stash = ["git", "stash"].join(" ");

test("guard refuses a pathless git stash and allows a harmless command", async () => {
	const refusal = await checkCommand(stash, "/realm/tmp/work/scratch-repo");
	assert.match(refusal, /git stash without paths blocked/);
	assert.equal(await checkCommand("git status --short", "/realm/tmp/work/scratch-repo"), undefined);
	assert.equal(await checkCommand(`${stash} push -m wip -- a.txt`, "/realm/tmp/work/scratch-repo"), undefined);
	const polling = await checkCommand("until test -s out; do sleep 30; done", "/tmp");
	assert.match(polling, /Run the blocking command itself/);
	assert.doesNotMatch(polling, /run_in_background|exec session/);
});

test("guard handler blocks through pi's tool_call event, for bash only", async () => {
	const { pi, fire } = fakePi();
	guard(pi);
	const bash = (command) => ({ type: "tool_call", toolName: "bash", toolCallId: "1", input: { command } });
	const blocked = await fire("tool_call", bash(forcePush), { cwd: "/tmp" });
	assert.equal(blocked.block, true);
	assert.match(blocked.reason, /force/i);
	assert.equal(await fire("tool_call", bash("ls"), { cwd: "/tmp" }), undefined);
	const read = { type: "tool_call", toolName: "read", toolCallId: "2", input: { path: stash } };
	assert.equal(await fire("tool_call", read, { cwd: "/tmp" }), undefined);
});

test("a guard that cannot run refuses the command", async () => {
	assert.match(await checkCommand("ls", "/tmp", "/nonexistent/guard.py"), /could not run/);
});

test("ask_operator returns the picked choice, a typed answer, or a dismissal as data", async () => {
	const { pi, state } = fakePi();
	ask(pi);
	const tool = state.tools.get("ask_operator");
	assert.deepEqual(tool.parameters.required, ["deciding", "why", "recommendation", "choices"]);
	const question = {
		deciding: "Which store holds the notes?",
		why: "It fixes the backup route.",
		recommendation: "The local store, because it needs no network.",
		choices: [{ label: "Local store" }, { label: "Remote store", consequence: "Needs a token." }],
		recommended: 1,
	};
	const picked = fakeContext(state, ["2. Remote store"]);
	const first = await tool.execute("1", question, undefined, undefined, picked.ctx);
	assert.deepEqual(first.structuredContent, { answered: true, choice: 2, label: "Remote store" });
	const shown = picked.seen.selects[0];
	assert.match(shown.title, /Which store holds the notes\?\nWhy it matters: .*\nRecommendation: /);
	assert.deepEqual(shown.options, ["1. Local store (recommended)", "2. Remote store", "t. Type an answer"]);

	const typed = fakeContext(state, ["t. Type an answer", "neither, use paper"]);
	const second = await tool.execute("2", question, undefined, undefined, typed.ctx);
	assert.deepEqual(second.structuredContent, { answered: true, text: "neither, use paper" });

	const dismissed = fakeContext(state, [undefined]);
	const third = await tool.execute("3", question, undefined, undefined, dismissed.ctx);
	assert.deepEqual(third.structuredContent, { answered: false });

	const headless = fakeContext(state, [], { mode: "print", hasUI: false });
	await assert.rejects(tool.execute("4", question, undefined, undefined, headless.ctx), /needs an operator/);
});

test("the questions preset limits tools, adds its instructions and drops the global file", async () => {
	const questions = loadPresets().get("questions");
	assert.ok(questions.instructions.includes("ask_operator"));
	for (const coding of ["bash", "edit", "write"]) assert.ok(!questions.tools.includes(coding));

	const { pi, state, fire } = fakePi({ preset: "questions" });
	ask(pi);
	compare(pi);
	presets(pi);
	assert.ok(state.flags.has("preset") && state.commands.has("preset"));
	const { ctx, seen } = fakeContext(state);
	await fire("session_start", { reason: "startup" }, ctx);
	assert.deepEqual(state.active, ["read", "grep", "find", "ls", "ask_operator", "rank_options"]);
	assert.equal(seen.status.preset, "preset: questions");
	assert.deepEqual(state.entries.at(-1).data, { name: "questions" });

	const options = () => ({
		sections: {},
		contextFiles: [
			{ path: join(agentDir, "AGENTS.md"), content: "global" },
			{ path: "/some/project/AGENTS.md", content: "project" },
		],
	});
	state.active.push("tool_search");
	const during = { systemPromptOptions: options() };
	await fire("before_agent_start", during, ctx);
	assert.deepEqual(
		during.systemPromptOptions.contextFiles.map((file) => file.content),
		["project"],
	);
	assert.equal(during.systemPromptOptions.sections.preset, questions.instructions);
	assert.ok(!state.active.includes("tool_search"));

	await state.commands.get("preset").handler("off", ctx);
	assert.deepEqual(state.active, ["read", "bash", "edit", "write"]);
	const after = { systemPromptOptions: options() };
	await fire("before_agent_start", after, ctx);
	assert.equal(after.systemPromptOptions.contextFiles.length, 2);
	assert.equal(after.systemPromptOptions.sections.preset, undefined);

	// A resumed session comes back in the preset it recorded, without the flag.
	const resumed = fakePi();
	ask(resumed.pi);
	compare(resumed.pi);
	presets(resumed.pi);
	resumed.state.entries.push({ type: "custom", customType: "sinnix-preset", data: { name: "questions" } });
	await resumed.fire("session_start", { reason: "resume" }, fakeContext(resumed.state).ctx);
	assert.ok(resumed.state.active.includes("ask_operator") && !resumed.state.active.includes("bash"));
});

const fiveItems = [
	{ id: "opt-alpha", label: "Alpha: plain text list" },
	{ id: "opt-bravo", label: "Bravo: side panel", meta: { note: "needs a wide terminal" } },
	{ id: "opt-charlie", label: "Charlie: web page" },
	{ id: "opt-delta", label: "Delta: phone deck" },
	{ id: "opt-echo", label: "Echo: printed sheet" },
];
const liveComparisons = (domain) => {
	const file = join(process.env.SINNIX_RANK_ROOT, domain, "comparisons.jsonl");
	const records = readFileSync(file, "utf8")
		.trim()
		.split("\n")
		.filter(Boolean)
		.map((line) => JSON.parse(line));
	const retracted = new Set(records.filter((record) => record.delete).map((record) => record.delete));
	return records.filter((record) => !record.delete && !retracted.has(record.id));
};

test("a sitting records only the operator's keys, one engine call per answer, and undoes", async () => {
	let calls = 0;
	const engine = new RankEngine((command, args) => (calls++, exec(command, args)));
	await engine.add("sitting", fiveItems);
	const sitting = await Sitting.open(engine, "sitting", { max: 3 });
	calls = 0;
	const first = sitting.current.set.map((item) => item.id);
	await sitting.apply(actionForKey("left", sitting.current.set));
	assert.equal(calls, 1);
	assert.deepEqual(
		liveComparisons("sitting").map((comparison) => [comparison.set, comparison.winner]),
		[[first, first[0]]],
	);
	await sitting.apply(actionForKey("u", sitting.current.set));
	assert.equal(calls, 2);
	assert.equal(liveComparisons("sitting").length, 0);
	assert.equal(sitting.chosen, 0);
	await sitting.apply(actionForKey("s", sitting.current.set));
	assert.equal(liveComparisons("sitting")[0].kind, "skip");
	for (let round = 0; round < 3; round++) await sitting.apply(actionForKey("2", sitting.current.set));
	assert.equal(sitting.ended, "limit reached");
	assert.equal(sitting.summary().comparisons_this_sitting, 3);
	assert.equal(sitting.current.evidence.operator_comparisons, 3);
});

test("rank_options registers options, runs the sitting for the operator and returns the fitted order", async () => {
	const { pi, state } = fakePi();
	compare(pi);
	const tool = state.tools.get("rank_options");
	// This operator always prefers the alphabetically earlier label.
	const prefer = (options) =>
		options.filter((option) => /^\d/.test(option)).sort((a, b) => a.slice(3).localeCompare(b.slice(3)))[0];
	const { ctx, seen } = fakeContext(state, Array(8).fill(prefer));
	const request = { domain: "tool", items: fiveItems, max_comparisons: 8 };
	const result = await tool.execute("1", request, undefined, undefined, ctx);
	const data = result.structuredContent;
	assert.equal(liveComparisons("tool").length, data.comparisons_this_sitting);
	assert.ok(data.comparisons_this_sitting >= 4 && data.comparisons_this_sitting <= 8);
	assert.equal(data.order[0].id, "opt-alpha");
	assert.equal(data.order.length, 5);
	assert.equal(typeof data.settled, "boolean");
	assert.match(seen.selects[0].title, /Which do you prefer\? \(tool\)/);
	assert.ok(seen.selects[0].options.includes("s. Skip") && seen.selects[0].options.includes("q. Quit"));
	if (process.env.SINNIX_PI_TEST_SHOW) console.log(JSON.stringify(data, null, 2));

	// Quitting at once records nothing and still reports the order as it stands.
	const recorded = liveComparisons("tool").length;
	const quit = fakeContext(state, ["q. Quit"]);
	const again = await tool.execute("2", { domain: "tool" }, undefined, undefined, quit.ctx);
	assert.equal(again.structuredContent.comparisons_this_sitting, 0);
	assert.equal(liveComparisons("tool").length, recorded);

	const headless = fakeContext(state, [], { mode: "json", hasUI: false });
	await assert.rejects(tool.execute("3", { domain: "tool" }, undefined, undefined, headless.ctx), /needs an operator/);
});

test("/compare runs the same sitting from a command", async () => {
	const { pi, state } = fakePi();
	compare(pi);
	const engine = new RankEngine(exec);
	await engine.add("command", fiveItems);
	const { ctx, seen } = fakeContext(state, [(options) => options[0], (options) => options[1], "q. Quit"]);
	await state.commands.get("compare").handler("command", ctx);
	assert.equal(liveComparisons("command").length, 2);
	assert.match(seen.notes.at(-1).message, /command: 2 compared, operator quit/);
});

test("items with a path show the file's size, date and a text preview", async () => {
	const file = join(agentDir, "note.txt");
	writeFileSync(file, "first line\nsecond line\n");
	const item = { id: "f", label: "a file", meta: { path: file, owner: "nobody" } };
	assert.ok(fileDisplay.applies(item));
	const lines = await describeItem(item);
	assert.equal(lines[0], file);
	assert.match(lines[1], /^23 B, modified \d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
	assert.deepEqual(lines.slice(2, 4), ["| first line", "| second line"]);
	assert.ok(lines.includes("owner: nobody"));
	mkdirSync(join(agentDir, "folder"), { recursive: true });
	const folder = await describeItem({ id: "d", label: "a folder", meta: { path: join(agentDir, "folder") } });
	assert.match(folder[1], /^directory, 0 entries, modified /);
	assert.deepEqual(await describeItem({ id: "t", label: "text", meta: { note: "n" } }), ["note: n"]);
});

test("sets are laid out side by side, or stacked when the terminal is narrow", () => {
	const left = { heading: "[1] Left option", details: ["detail", `| ${"x".repeat(60)}`] };
	const rows = sideBySide([left, { heading: "[2] Right option", details: [] }], 80);
	assert.equal(rows.length, 3);
	assert.match(rows[0], /^\[1\] Left option\s+\[2\] Right option$/);
	assert.equal(rows[0].indexOf("[2]"), 41);
	// A long preview line is cut at the column edge instead of pushing rows down.
	assert.ok(rows[2].startsWith("| xxxx") && !rows[2].includes("x".repeat(38)));
	const stacked = sideBySide([{ heading: "a", details: ["one"] }, { heading: "b", details: [] }], 30);
	assert.deepEqual(stacked, ["a", "one", "", "b"]);
});

test("a Claude Code reply charged to usage credits stops the run", async () => {
	const reply = (details) => ({
		role: "assistant",
		provider: "claude-code",
		diagnostics: [{ type: "claude-code.rate-limit", details }],
	});
	assert.ok(chargedToUsageCredits(reply({ status: "allowed", rateLimitType: "overage" })));
	assert.ok(chargedToUsageCredits(reply({ overageInUse: true })));
	assert.ok(!chargedToUsageCredits(reply({ status: "allowed", rateLimitType: "five_hour" })));
	assert.ok(!chargedToUsageCredits({ ...reply({ rateLimitType: "overage" }), provider: "openai" }));
	const { pi, state, fire } = fakePi();
	planBilling(pi);
	const { ctx, seen } = fakeContext(state);
	await fire("message_end", { message: reply({ rateLimitType: "overage" }) }, ctx);
	assert.equal(seen.aborted, true);
	assert.match(seen.notes[0].message, /usage credits/);
});

if (process.argv.includes("--schemas")) {
	const { pi, state } = fakePi();
	ask(pi);
	compare(pi);
	const tools = [...state.tools.values()].map(({ name, description, parameters }) => ({
		name,
		description,
		parameters,
	}));
	const listed = [...loadPresets().values()].map(({ name, description, tools: names }) => ({
		name,
		description,
		tools: names,
	}));
	console.log(JSON.stringify({ tools, presets: listed }, null, 2));
} else {
	let failed = 0;
	for (const [name, body] of tests) {
		try {
			await body();
			console.log(`ok   ${name}`);
		} catch (error) {
			failed++;
			console.log(`FAIL ${name}\n${error.stack}`);
		}
	}
	process.exit(failed ? 1 : 0);
}
