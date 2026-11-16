/**
 * Pairwise comparison: `/compare <domain>` and the `rank_options` tool.
 *
 * Both run the same sitting over a `sinnix-rank` domain. The operator sees
 * the current set side by side and answers with one key; each answer is one
 * `sinnix-rank` call and no model turn. Only keys the operator presses are
 * recorded: the model can register options and read the fitted order, never
 * add a comparison.
 *
 * In the terminal the sitting is one component that stays open. Other front
 * ends get the same sitting as a series of `select` dialogs.
 */

import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { truncateToWidth, visibleWidth, wrapTextWithAnsi } from "@earendil-works/pi-tui";
import { Type } from "typebox";
import { keyOf } from "../lib/choice.ts";
import { describeItem } from "../lib/item-display.ts";
import { type Action, type Evidence, type NextSet, RankEngine, type RankItem, Sitting } from "../lib/rank.ts";

const MIN_COLUMN = 28;
const GAP = "   ";

export interface Column {
	/** Wrapped when it does not fit. */
	heading: string;
	/** One row each; cut at the column edge, so a preview keeps its line structure. */
	details: string[];
}

/** Columns laid out next to each other, or under each other when too narrow. */
export function sideBySide(columns: Column[], width: number): string[] {
	const side = Math.floor((width - GAP.length * (columns.length - 1)) / columns.length);
	const columnWidth = side < MIN_COLUMN ? width : side;
	const cells = columns.map((column) => [
		...wrapTextWithAnsi(column.heading, columnWidth),
		...column.details.map((line) => truncateToWidth(line, columnWidth)),
	]);
	if (side < MIN_COLUMN) {
		return cells.flatMap((column, index) => [...column, ...(index < cells.length - 1 ? [""] : [])]);
	}
	const height = Math.max(...cells.map((column) => column.length));
	const rows: string[] = [];
	for (let row = 0; row < height; row++) {
		rows.push(
			cells
				.map((column) => {
					const cell = column[row] ?? "";
					return cell + " ".repeat(Math.max(0, columnWidth - visibleWidth(cell)));
				})
				.join(GAP)
				.trimEnd(),
		);
	}
	return rows;
}

export function progressLine(sitting: Sitting): string {
	const evidence = sitting.current.evidence;
	const state = evidence.settled ? "evidence settled" : `not settled: ${evidence.reasons[0] ?? "more comparisons needed"}`;
	const skipped = sitting.skipped > 0 ? `, ${sitting.skipped} skipped` : "";
	return `${sitting.chosen} compared this sitting${skipped} | ${evidence.operator_comparisons} in the domain | ${state}`;
}

/** The action a key means for the current set, if any. */
export function actionForKey(key: string, set: RankItem[]): Action | undefined {
	if (key === "s") return { kind: "skip" };
	if (key === "u") return { kind: "undo" };
	if (key === "q" || key === "escape") return { kind: "quit" };
	let index = /^[1-9]$/.test(key) ? Number(key) - 1 : -1;
	if (set.length === 2 && key === "left") index = 0;
	if (set.length === 2 && key === "right") index = 1;
	return set[index] ? { kind: "choose", winner: set[index].id } : undefined;
}

async function describeSet(set: NextSet): Promise<string[][]> {
	return Promise.all(set.set.map((item) => describeItem(item)));
}

function keyHints(set: RankItem[]): string {
	const pick = set.length === 2 ? "[1] or [left], [2] or [right] pick" : `[1]-[${set.length}] pick`;
	return `${pick}   [s] skip   [u] undo   [q] quit`;
}

async function runInTerminal(ctx: ExtensionContext, sitting: Sitting): Promise<void> {
	let details = await describeSet(sitting.current);
	await ctx.ui.custom<void>(
		(tui, theme, _keybindings, done) => {
			let busy = false;
			let note = "";
			const act = async (action: Action) => {
				busy = true;
				note = "";
				tui.requestRender();
				try {
					await sitting.apply(action);
					if (sitting.ended) return done();
					details = await describeSet(sitting.current);
				} catch (error) {
					note = (error as Error).message;
				}
				busy = false;
				tui.requestRender();
			};
			return {
				render(width: number): string[] {
					const set = sitting.current.set;
					const columns = set.map((item, index) => ({
						heading: theme.fg("accent", theme.bold(`[${index + 1}] ${item.label}`)),
						details: details[index].map((line) => theme.fg("muted", line)),
					}));
					const lines = [
						theme.fg("accent", theme.bold(`Which do you prefer? (${sitting.current.domain})`)),
						"",
						...sideBySide(columns, width),
						"",
						theme.fg("dim", busy ? "recording..." : keyHints(set)),
						theme.fg("dim", progressLine(sitting)),
					];
					if (note) lines.push(theme.fg("error", note));
					return lines.map((line) => truncateToWidth(line, width));
				},
				handleInput(data: string): void {
					if (busy) return;
					const action = actionForKey(keyOf(data), sitting.current.set);
					if (action?.kind === "undo" && !sitting.canUndo) return;
					if (action) void act(action);
				},
				invalidate() {},
			};
		},
		{ blocked: { kind: "question", message: `Comparing options in ${sitting.current.domain}` } },
	);
}

async function runWithDialogs(ctx: ExtensionContext, sitting: Sitting): Promise<void> {
	while (!sitting.ended) {
		const set = sitting.current.set;
		const details = await describeSet(sitting.current);
		const body = set.flatMap((item, index) => [`${index + 1}. ${item.label}`, ...details[index].map((line) => `   ${line}`)]);
		const options = [
			...set.map((item, index) => `${index + 1}. ${item.label}`),
			"s. Skip",
			...(sitting.canUndo ? ["u. Undo"] : []),
			"q. Quit",
		];
		const title = [`Which do you prefer? (${sitting.current.domain})`, ...body, progressLine(sitting)].join("\n");
		const picked = await ctx.ui.select(title, options);
		const action = picked === undefined ? ({ kind: "quit" } as Action) : actionForKey(picked[0], set);
		if (action) await sitting.apply(action);
	}
}

/** Run one sitting for the operator in whatever front end this session has. */
export async function runSitting(
	ctx: ExtensionContext,
	engine: RankEngine,
	domain: string,
	options: { max?: number; stopWhenSettled?: boolean },
): Promise<Sitting> {
	const sitting = await Sitting.open(engine, domain, options);
	if (sitting.ended) return sitting;
	if (ctx.mode === "tui") await runInTerminal(ctx, sitting);
	else await runWithDialogs(ctx, sitting);
	return sitting;
}

function settledSentence(evidence: Evidence): string {
	return evidence.settled
		? "The evidence is settled."
		: `The order is provisional: ${evidence.reasons.join("; ")}.`;
}

const rankParameters = Type.Object({
	domain: Type.String({
		description: "Name of the ranking domain, stable across sessions, such as design-directions. Reuse it to resume.",
	}),
	items: Type.Optional(
		Type.Array(
			Type.Object({
				id: Type.String({ description: "Stable, meaningful id such as opt-hub-page; never a position number." }),
				label: Type.String({ description: "The option as the operator should read it." }),
				meta: Type.Optional(
					Type.Record(Type.String(), Type.Unknown(), {
						description: "Extra facts shown with the option. A `path` shows that file's size, date and a preview.",
					}),
				),
			}),
			{ description: "Options to register before comparing. Already registered ids are left as they are." },
		),
	),
	max_comparisons: Type.Optional(
		Type.Integer({ minimum: 1, maximum: 200, description: "Most comparisons to ask for in this sitting. Default 10." }),
	),
});

export default function compare(pi: ExtensionAPI) {
	const engine = new RankEngine((command, args) => pi.exec(command, args));

	pi.registerCommand("compare", {
		description: "Compare the options of a ranking domain, one key per answer: /compare <domain> [max]",
		handler: async (args, ctx) => {
			const [domain, limit] = (args ?? "").trim().split(/\s+/);
			if (!domain) {
				ctx.ui.notify("Usage: /compare <domain> [max]. `sinnix-rank list` shows the domains.", "warning");
				return;
			}
			if (!ctx.hasUI) return;
			try {
				const max = limit ? Number(limit) : undefined;
				const sitting = await runSitting(ctx, engine, domain, { max: Number.isFinite(max) ? max : undefined });
				const summary = sitting.summary();
				ctx.ui.notify(
					`${domain}: ${summary.comparisons_this_sitting} compared, ${summary.stopped_because}. ` +
						`${settledSentence(summary.evidence)} Order: sinnix-rank status ${domain}`,
					"info",
				);
			} catch (error) {
				ctx.ui.notify((error as Error).message, "error");
			}
		},
	});

	pi.registerTool({
		name: "rank_options",
		label: "Rank options",
		description:
			"Have the operator order options by preference. Registers any new options in a ranking domain, shows " +
			"the operator sets to compare (one key each, no model involved), and returns the fitted order with the " +
			"evidence behind it. Only the operator's own choices are recorded.",
		promptSnippet: "Have the operator order several options by pairwise comparison and get the fitted order",
		promptGuidelines: [
			"Use rank_options when the operator must order three or more options by preference; do not guess the order or ask about pairs in prose.",
			"Report a rank_options order as provisional unless its evidence says settled.",
		],
		parameters: rankParameters,
		outputSchema: Type.Object({
			domain: Type.String(),
			order: Type.Array(
				Type.Object({
					id: Type.String(),
					label: Type.String(),
					theta: Type.Number({ description: "Fitted strength; higher is preferred." }),
					se: Type.Number({ description: "Standard error; large means the position is a guess." }),
					matches: Type.Number(),
				}),
			),
			top_stability: Type.Number({ description: "Share of posterior samples with the same top option." }),
			settled: Type.Boolean({ description: "Whether the comparisons support the order at all." }),
			reasons: Type.Array(Type.String(), { description: "Why not, when not settled." }),
			comparisons_this_sitting: Type.Integer(),
			stopped_because: Type.String(),
			resume: Type.String({ description: "Command that shows the current order." }),
		}),
		executionMode: "sequential",

		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			if (!ctx.hasUI) throw new Error("rank_options needs an operator: this run has no way to show a comparison.");
			if (params.items?.length) await engine.add(params.domain, params.items as RankItem[]);
			const sitting = await runSitting(ctx, engine, params.domain, {
				max: params.max_comparisons ?? 10,
				stopWhenSettled: true,
			});
			const summary = sitting.summary();
			const status = await engine.status(params.domain);
			const result = {
				domain: params.domain,
				order: status.items.map(({ id, label, theta, se, matches }) => ({ id, label, theta, se, matches })),
				top_stability: status.stability.p_stable,
				settled: status.evidence.settled,
				reasons: status.evidence.reasons,
				comparisons_this_sitting: summary.comparisons_this_sitting,
				stopped_because: summary.stopped_because,
				resume: `sinnix-rank status ${params.domain} --json`,
			};
			const listing = result.order.map((item, index) => `${index + 1}. ${item.label} [${item.id}]`).join("\n");
			return {
				content: [
					{
						type: "text",
						text:
							`${summary.comparisons_this_sitting} comparisons this sitting (${summary.stopped_because}). ` +
							`${settledSentence(status.evidence)}\n${listing}`,
					},
				],
				details: result,
				structuredContent: result,
			};
		},
	});
}
