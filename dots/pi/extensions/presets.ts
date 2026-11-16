/**
 * Presets: named modes with their own instructions, tools and model.
 *
 * Pi has no built-in notion of a mode, so this extension provides one. A
 * preset is a JSON file in ../presets naming an instruction file, a tool
 * list, and optionally a model and thinking level. `pi --preset <name>`
 * starts in it; `/preset <name>` and `/preset off` switch during a session,
 * and a resumed session comes back in the preset it was left in.
 *
 * While a preset is active the model gets the preset's instructions as a
 * `preset` section of the system prompt, exactly the listed tools, and not
 * the global instruction file from pi's agent directory, which is written
 * for coding work. Project instruction files still load.
 */

import { readdirSync, readFileSync, realpathSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { type ExtensionAPI, type ExtensionContext, getAgentDir } from "@earendil-works/pi-coding-agent";

export interface Preset {
	name: string;
	description: string;
	/** Text of the instruction file. */
	instructions: string;
	tools: string[];
	/** "provider/model-id"; the session's model when absent. */
	model?: string;
	thinking?: "off" | "minimal" | "low" | "medium" | "high" | "xhigh" | "max";
}

const ENTRY_TYPE = "sinnix-preset";
const OFF = "off";

export function presetsDir(): string {
	return resolve(dirname(realpathSync(fileURLToPath(import.meta.url))), "../presets");
}

export function loadPresets(dir = presetsDir()): Map<string, Preset> {
	const presets = new Map<string, Preset>();
	for (const file of readdirSync(dir).sort()) {
		if (!file.endsWith(".json")) continue;
		const name = basename(file, ".json");
		const declared = JSON.parse(readFileSync(join(dir, file), "utf8"));
		if (!Array.isArray(declared.tools) || typeof declared.instructions !== "string") {
			throw new Error(`preset ${name}: needs "instructions" (a file name) and "tools" (a list)`);
		}
		presets.set(name, {
			name,
			description: String(declared.description ?? name),
			instructions: readFileSync(join(dir, declared.instructions), "utf8").trim(),
			tools: declared.tools,
			model: declared.model,
			thinking: declared.thinking,
		});
	}
	return presets;
}

function sameDirectory(path: string, directory: string): boolean {
	try {
		return realpathSync(dirname(path)) === realpathSync(directory);
	} catch {
		return dirname(path) === directory;
	}
}

export default function presets(pi: ExtensionAPI) {
	const available = loadPresets();
	let active: Preset | undefined;
	let before: { tools: string[]; model: ExtensionContext["model"]; thinking: Preset["thinking"] } | undefined;

	pi.registerFlag("preset", {
		description: `Start in a preset (${[...available.keys()].join(", ")})`,
		type: "string",
	});

	function knownTools(preset: Preset): string[] {
		const registered = new Set(pi.getAllTools().map((tool) => tool.name));
		return preset.tools.filter((tool) => registered.has(tool));
	}

	async function activate(preset: Preset, ctx: ExtensionContext, record: boolean): Promise<void> {
		before ??= { tools: pi.getActiveTools(), model: ctx.model, thinking: pi.getThinkingLevel() };
		if (preset.model) {
			const [provider, ...id] = preset.model.split("/");
			const model = ctx.modelRegistry.find(provider, id.join("/"));
			if (!model || !(await pi.setModel(model))) {
				ctx.ui.notify(`Preset ${preset.name}: model ${preset.model} is not available; keeping the current one.`, "warning");
			}
		}
		if (preset.thinking) pi.setThinkingLevel(preset.thinking);
		pi.setActiveTools(knownTools(preset));
		active = preset;
		if (record) pi.appendEntry(ENTRY_TYPE, { name: preset.name });
		ctx.ui.setStatus("preset", `preset: ${preset.name}`);
	}

	async function deactivate(ctx: ExtensionContext, record: boolean): Promise<void> {
		if (before) {
			if (before.model) await pi.setModel(before.model);
			if (before.thinking) pi.setThinkingLevel(before.thinking);
			pi.setActiveTools(before.tools);
		}
		active = undefined;
		before = undefined;
		if (record) pi.appendEntry(ENTRY_TYPE, { name: OFF });
		ctx.ui.setStatus("preset", undefined);
	}

	/** The preset this session was last left in, from its own record. */
	function recorded(ctx: ExtensionContext): string | undefined {
		let name: string | undefined;
		for (const entry of ctx.sessionManager.getEntries() as Array<{ type: string; customType?: string; data?: any }>) {
			if (entry.type === "custom" && entry.customType === ENTRY_TYPE) name = entry.data?.name;
		}
		return name;
	}

	pi.on("session_start", async (_event, ctx) => {
		const flagged = pi.getFlag("preset");
		const wanted = recorded(ctx) ?? (typeof flagged === "string" ? flagged : undefined);
		if (!wanted || wanted === OFF) return;
		const preset = available.get(wanted);
		if (!preset) {
			ctx.ui.notify(`Unknown preset "${wanted}". Available: ${[...available.keys()].join(", ")}`, "error");
			return;
		}
		await activate(preset, ctx, recorded(ctx) !== wanted);
	});

	pi.on("before_agent_start", async (event) => {
		const options = event.systemPromptOptions;
		if (!active) {
			delete options.sections?.preset;
			return;
		}
		const agentDir = getAgentDir();
		const files = options.contextFiles ?? [];
		for (let index = files.length - 1; index >= 0; index--) {
			if (sameDirectory(files[index].path, agentDir)) files.splice(index, 1);
		}
		options.sections ??= {};
		options.sections.preset = active.instructions;
		// A tool server that connects late can switch tools on; the preset's list wins.
		pi.setActiveTools(knownTools(active));
	});

	pi.registerCommand("preset", {
		description: `Switch preset: ${[...available.keys()].join(", ")}, or ${OFF}`,
		getArgumentCompletions: (prefix: string) => {
			const matches = [...available.keys(), OFF].filter((name) => name.startsWith(prefix));
			return matches.length > 0 ? matches.map((name) => ({ value: name, label: name })) : null;
		},
		handler: async (args, ctx) => {
			let wanted = args?.trim();
			if (!wanted) {
				const listing = [...available.values()].map((preset) => `${preset.name}: ${preset.description}`);
				if (!ctx.hasUI) return;
				const picked = await ctx.ui.select(`Preset (now: ${active?.name ?? OFF})`, [...listing, OFF]);
				if (picked === undefined) return;
				wanted = picked.split(":")[0];
			}
			if (wanted === OFF) {
				await deactivate(ctx, true);
				ctx.ui.notify("Preset off: general instructions and tools restored.", "info");
				return;
			}
			const preset = available.get(wanted);
			if (!preset) {
				ctx.ui.notify(`Unknown preset "${wanted}". Available: ${[...available.keys()].join(", ")}`, "error");
				return;
			}
			await activate(preset, ctx, true);
			ctx.ui.notify(`Preset ${preset.name}: ${preset.description}`, "info");
		},
	});
}
