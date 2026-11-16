/**
 * The ranking engine, reached through its command line.
 *
 * `sinnix-rank` owns the store, the choice of what to ask next and the fit.
 * Nothing here scores, orders or stores anything; it only calls the commands
 * and reads their JSON. `record --next` and `retract --next` answer with the
 * following set and the evidence so far, so a comparison loop costs one
 * process per answer.
 */

import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

export interface RankItem {
	id: string;
	label: string;
	meta?: Record<string, unknown>;
}

export interface Evidence {
	items: number;
	operator_comparisons: number;
	settled: boolean;
	reasons: string[];
	[key: string]: unknown;
}

export interface NextSet {
	domain: string;
	strategy: string;
	already_judged: boolean;
	set: RankItem[];
	evidence: Evidence;
}

export interface RankStatus {
	domain: string;
	items: Array<{ id: string; label: string; theta: number; se: number; matches: number; component: number }>;
	stability: { top_k: string[]; p_stable: number; k: number };
	evidence: Evidence;
	[key: string]: unknown;
}

/** Runs a command without a shell; pi's `pi.exec` has this shape. */
export type Exec = (command: string, args: string[]) => Promise<{ stdout: string; stderr: string; code: number }>;

export const RANK_COMMAND = "sinnix-rank";

export class RankEngine {
	private readonly exec: Exec;

	constructor(exec: Exec) {
		this.exec = exec;
	}

	private async run(args: string[]): Promise<string> {
		const result = await this.exec(RANK_COMMAND, args);
		if (result.code !== 0) {
			throw new Error(`sinnix-rank ${args[0]} failed: ${(result.stderr || result.stdout).trim()}`);
		}
		return result.stdout;
	}

	async next(domain: string, grid = 2): Promise<NextSet> {
		return JSON.parse(await this.run(["next", domain, "--json", "--grid", String(grid)]));
	}

	/** One operator judgment. `winner` undefined records that the operator skipped the set. */
	async record(
		domain: string,
		set: string[],
		winner: string | undefined,
		context: string,
	): Promise<{ comparison: string; next: NextSet }> {
		const judgment = winner === undefined ? ["--kind", "skip"] : ["--winner", winner];
		const args = ["record", domain, "--set", set.join(","), ...judgment, "--context", context];
		return JSON.parse(await this.run([...args, "--next", "--grid", String(set.length)]));
	}

	async retract(domain: string, comparison: string, grid = 2): Promise<{ retracted: string; next: NextSet }> {
		return JSON.parse(
			await this.run(["retract", domain, "--comparison", comparison, "--next", "--grid", String(grid)]),
		);
	}

	async add(domain: string, items: RankItem[]): Promise<string> {
		const directory = await mkdtemp(join(tmpdir(), "pi-rank-"));
		try {
			const file = join(directory, "items.jsonl");
			const lines = items.map((item) => JSON.stringify({ ...(item.meta ?? {}), id: item.id, label: item.label }));
			await writeFile(file, `${lines.join("\n")}\n`);
			return (await this.run(["add", domain, "--items", file])).trim();
		} finally {
			await rm(directory, { recursive: true, force: true });
		}
	}

	async status(domain: string): Promise<RankStatus> {
		return JSON.parse(await this.run(["status", domain, "--json"]));
	}
}

export type Action = { kind: "choose"; winner: string } | { kind: "skip" } | { kind: "undo" } | { kind: "quit" };

export interface SittingOptions {
	/** Stop after this many recorded choices. */
	max?: number;
	/** Stop as soon as the engine reports the evidence settled. */
	stopWhenSettled?: boolean;
	/** Items per set; 2 is pairwise. */
	grid?: number;
}

export interface SittingSummary {
	domain: string;
	comparisons_this_sitting: number;
	skipped_this_sitting: number;
	stopped_because: "operator quit" | "limit reached" | "evidence settled";
	evidence: Evidence;
}

/**
 * One sitting of comparisons over a domain: the current set, the operator's
 * actions, and the count. Front ends show `current` and call `apply`; they
 * hold no ranking state of their own.
 */
export class Sitting {
	current: NextSet;
	chosen = 0;
	skipped = 0;
	/** Why the sitting ended, once it has. */
	ended: SittingSummary["stopped_because"] | undefined;
	private readonly engine: RankEngine;
	private readonly options: SittingOptions;
	private readonly context: string;
	private readonly recorded: Array<{ id: string; skip: boolean }> = [];

	private constructor(engine: RankEngine, first: NextSet, options: SittingOptions) {
		this.engine = engine;
		this.current = first;
		this.options = options;
		this.context = `pi sitting ${new Date().toISOString().slice(0, 16)}Z`;
		this.checkEnd();
	}

	static async open(engine: RankEngine, domain: string, options: SittingOptions = {}): Promise<Sitting> {
		return new Sitting(engine, await engine.next(domain, options.grid ?? 2), options);
	}

	get canUndo(): boolean {
		return this.recorded.length > 0;
	}

	async apply(action: Action): Promise<void> {
		const domain = this.current.domain;
		const ids = this.current.set.map((item) => item.id);
		if (action.kind === "quit") {
			this.ended = "operator quit";
			return;
		}
		if (action.kind === "undo") {
			const last = this.recorded.pop();
			if (!last) return;
			this.current = (await this.engine.retract(domain, last.id, ids.length)).next;
			if (last.skip) this.skipped--;
			else this.chosen--;
			return;
		}
		const winner = action.kind === "choose" ? action.winner : undefined;
		const answer = await this.engine.record(domain, ids, winner, this.context);
		this.recorded.push({ id: answer.comparison, skip: winner === undefined });
		if (winner === undefined) this.skipped++;
		else this.chosen++;
		this.current = answer.next;
		this.checkEnd();
	}

	private checkEnd(): void {
		if (this.options.stopWhenSettled && this.current.evidence.settled) this.ended = "evidence settled";
		else if (this.options.max !== undefined && this.chosen >= this.options.max) this.ended = "limit reached";
	}

	summary(): SittingSummary {
		return {
			domain: this.current.domain,
			comparisons_this_sitting: this.chosen,
			skipped_this_sitting: this.skipped,
			stopped_because: this.ended ?? "operator quit",
			evidence: this.current.evidence,
		};
	}
}
