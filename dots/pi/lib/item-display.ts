/**
 * How one item of a comparison is shown.
 *
 * A display says whether it applies to an item and returns the lines to show
 * under the item's label. The first display that applies wins, so a new kind
 * of item (an image, a diff, a folder summary) is one more entry in
 * `displays`, ahead of the plain-text fallback.
 */

import { open, readdir, stat } from "node:fs/promises";
import type { RankItem } from "./rank.ts";

export interface ItemDisplay {
	name: string;
	applies(item: RankItem): boolean;
	/** Lines shown under the label; plain text, no styling. */
	describe(item: RankItem): Promise<string[]>;
}

const PREVIEW_LINES = 6;
const PREVIEW_BYTES = 2048;
const METADATA_LINES = 4;

function formatSize(bytes: number): string {
	const units = ["B", "KiB", "MiB", "GiB", "TiB"];
	let value = bytes;
	let unit = 0;
	while (value >= 1024 && unit < units.length - 1) {
		value /= 1024;
		unit++;
	}
	return `${unit === 0 ? value : value.toFixed(1)} ${units[unit]}`;
}

async function textPreview(path: string): Promise<string[]> {
	const handle = await open(path, "r");
	try {
		const buffer = Buffer.alloc(PREVIEW_BYTES);
		const { bytesRead } = await handle.read(buffer, 0, PREVIEW_BYTES, 0);
		const head = buffer.subarray(0, bytesRead);
		if (head.includes(0)) return [];
		return head
			.toString("utf8")
			.trimEnd()
			.split("\n")
			.slice(0, PREVIEW_LINES)
			.map((line) => `| ${line.replace(/\t/g, "  ")}`);
	} finally {
		await handle.close();
	}
}

/** Scalar metadata as `key: value` lines, leaving out what a display already showed. */
function metadataLines(item: RankItem, shown: string[] = []): string[] {
	return Object.entries(item.meta ?? {})
		.filter(([key, value]) => !shown.includes(key) && ["string", "number", "boolean"].includes(typeof value))
		.slice(0, METADATA_LINES)
		.map(([key, value]) => `${key}: ${value}`);
}

export const fileDisplay: ItemDisplay = {
	name: "file",
	applies: (item) => typeof item.meta?.path === "string",
	async describe(item) {
		const path = item.meta?.path as string;
		const lines = [path];
		try {
			const info = await stat(path);
			const modified = info.mtime.toISOString().slice(0, 16).replace("T", " ");
			if (info.isDirectory()) {
				lines.push(`directory, ${(await readdir(path)).length} entries, modified ${modified}`);
			} else {
				lines.push(`${formatSize(info.size)}, modified ${modified}`);
				lines.push(...(await textPreview(path)));
			}
		} catch (error) {
			lines.push(`unreadable: ${(error as NodeJS.ErrnoException).code ?? "error"}`);
		}
		return [...lines, ...metadataLines(item, ["path"])];
	},
};

export const textDisplay: ItemDisplay = {
	name: "text",
	applies: () => true,
	describe: async (item) => metadataLines(item),
};

/** In order of precedence; the last one accepts everything. */
export const displays: ItemDisplay[] = [fileDisplay, textDisplay];

export function describeItem(item: RankItem, available: ItemDisplay[] = displays): Promise<string[]> {
	return (available.find((display) => display.applies(item)) ?? textDisplay).describe(item);
}
