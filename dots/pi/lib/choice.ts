/**
 * One question, one key per answer.
 *
 * In the terminal this is a component that resolves on a single keypress.
 * Any other front end that can show dialogs gets pi's `select` (and `input`
 * for a typed answer), which RPC clients implement. Callers never touch the
 * terminal directly, so an interaction built on this works in both.
 */

import type { ExtensionContext } from "@earendil-works/pi-coding-agent";
import { parseKey, truncateToWidth, wrapTextWithAnsi } from "@earendil-works/pi-tui";

export interface KeyChoice {
	/** The single key that picks this choice, as pi names keys ("1", "a", "left"). */
	key: string;
	label: string;
	/** Extra lines shown under the label. */
	detail?: string[];
}

export interface ChoicePrompt {
	title: string;
	/** Lines shown above the choices. */
	body: string[];
	choices: KeyChoice[];
	/** Offer a typed answer as well (key "t"). */
	allowText?: boolean;
}

export type ChoiceAnswer = { kind: "choice"; key: string } | { kind: "text"; text: string } | { kind: "dismissed" };

const TEXT_KEY = "t";
const TEXT_LABEL = "Type an answer";

/** The key pi's parser reports, or the raw character for a plain keypress. */
export function keyOf(data: string): string {
	return (parseKey(data) ?? data).toLowerCase();
}

export function canAsk(ctx: ExtensionContext): boolean {
	return ctx.hasUI;
}

export async function askChoice(ctx: ExtensionContext, prompt: ChoicePrompt): Promise<ChoiceAnswer> {
	const picked = ctx.mode === "tui" ? await askInTerminal(ctx, prompt) : await askWithDialog(ctx, prompt);
	if (picked !== TEXT_KEY || !prompt.allowText) {
		return picked === undefined ? { kind: "dismissed" } : { kind: "choice", key: picked };
	}
	const text = (await ctx.ui.input(prompt.title, "your answer"))?.trim();
	return text ? { kind: "text", text } : { kind: "dismissed" };
}

async function askInTerminal(ctx: ExtensionContext, prompt: ChoicePrompt): Promise<string | undefined> {
	const keys = new Set(prompt.choices.map((choice) => choice.key));
	if (prompt.allowText) keys.add(TEXT_KEY);
	const result = await ctx.ui.custom<string | undefined>(
		(_tui, theme, _keybindings, done) => ({
			render(width: number): string[] {
				const lines: string[] = [theme.fg("accent", theme.bold(prompt.title)), ""];
				for (const line of prompt.body) lines.push(...wrapTextWithAnsi(line, width));
				lines.push("");
				for (const choice of prompt.choices) {
					lines.push(...wrapTextWithAnsi(`${theme.fg("accent", `[${choice.key}]`)} ${choice.label}`, width));
					for (const detail of choice.detail ?? []) {
						lines.push(...wrapTextWithAnsi(`    ${theme.fg("muted", detail)}`, width));
					}
				}
				const hints = [prompt.allowText ? `[${TEXT_KEY}] type an answer` : "", "[esc] dismiss"].filter(Boolean);
				lines.push("", theme.fg("dim", hints.join("   ")));
				return lines.map((line) => truncateToWidth(line, width));
			},
			handleInput(data: string): void {
				const key = keyOf(data);
				if (key === "escape") done(undefined);
				else if (keys.has(key)) done(key);
			},
			invalidate() {},
		}),
		{ blocked: { kind: "question", message: prompt.title } },
	);
	return result ?? undefined;
}

async function askWithDialog(ctx: ExtensionContext, prompt: ChoicePrompt): Promise<string | undefined> {
	const options = prompt.choices.map((choice) => `${choice.key}. ${choice.label}`);
	if (prompt.allowText) options.push(`${TEXT_KEY}. ${TEXT_LABEL}`);
	const title = [prompt.title, ...prompt.body].join("\n");
	const picked = await ctx.ui.select(title, options);
	if (picked === undefined) return undefined;
	return picked.slice(0, picked.indexOf("."));
}
