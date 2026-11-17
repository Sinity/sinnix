/** Compare several model continuations without collapsing them to a tiny label.
 * TUI renders full Markdown and scrolls. RPC receives full text through a
 * standard select dialog; neither branch needs a custom network/GUI service.
 */
import { Markdown, matchesKey, truncateToWidth } from "@earendil-works/pi-tui";
import { getMarkdownTheme, type ExtensionCommandContext } from "@earendil-works/pi-coding-agent";
import type { LoomCandidate } from "../extensions/loom.ts";

export async function chooseLoomBranch(
  ctx: ExtensionCommandContext, prompt: string, branches: LoomCandidate[],
): Promise<number | null> {
  if (!branches.length) return null;
  if (ctx.mode !== "tui") {
    const options = branches.map((branch, index) => {
      const label = String(index + 1) + ". " + branch.model.id;
      const text = branch.text.length > 5000
        ? branch.text.slice(0, 5000) + "\n[remaining text omitted from picker]" : branch.text;
      return label + "\n" + text;
    });
    const picked = await ctx.ui.select("Select one continuation of: " + prompt + "\nOther candidates stay available in /tree.", options);
    return picked !== undefined && options.includes(picked) ? options.indexOf(picked) : null;
  }

  return ctx.ui.custom<number | null>((tui, theme, _keys, done) => {
    let index = 0, offset = 0;
    const cache = new Map<string, string[]>();
    const markdown = getMarkdownTheme();
    function linesFor(width: number): string[] {
      const usableWidth = Math.max(18, width - 4);
      const key = String(index) + ":" + usableWidth;
      if (!cache.has(key)) {
        const md = new Markdown(branches[index].text, 0, 0, markdown);
        cache.set(key, md.render(usableWidth));
      }
      return cache.get(key)!;
    }
    return {
      render(width: number): string[] {
        const inner = Math.max(18, width - 4);
        const all = linesFor(width);
        const height = Math.max(5, (tui.terminal?.rows ?? 26) - 11);
        const shown = all.slice(offset, offset + height);
        const header = "Loom " + (index + 1) + "/" + branches.length +
          " · " + branches[index].model.id;
        const out = [
          "", "  " + theme.fg("accent", theme.bold(truncateToWidth(header, inner))),
          "  " + theme.fg("muted", truncateToWidth(prompt, inner)), "",
          "  " + theme.fg("dim", "─".repeat(inner)),
          ...shown.map(line => "  " + line),
        ];
        if (all.length > height) out.push(
          "  " + theme.fg("dim", String(offset + 1) + "–" + Math.min(offset + height, all.length) + "/" + all.length),
        );
        out.push("", "  " + theme.fg("muted", "←/→ alternate · ↑/↓ scroll · Enter choose · Esc cancel"), "");
        return out.map(line => truncateToWidth(line, Math.max(20, width)));
      },
      handleInput(data: string): void {
        const all = linesFor(tui.terminal?.columns ?? 80);
        const height = Math.max(5, (tui.terminal?.rows ?? 26) - 11);
        if (matchesKey(data, "escape")) done(null);
        else if (matchesKey(data, "return")) done(index);
        else if (matchesKey(data, "left") || data === "h") {
          index = (index + branches.length - 1) % branches.length; offset = 0; tui.requestRender();
        } else if (matchesKey(data, "right") || data === "l") {
          index = (index + 1) % branches.length; offset = 0; tui.requestRender();
        } else if (matchesKey(data, "up") || data === "k") {
          offset = Math.max(0, offset - 3); tui.requestRender();
        } else if (matchesKey(data, "down") || data === "j") {
          offset = Math.min(Math.max(0, all.length - height), offset + 3); tui.requestRender();
        }
      },
      invalidate(): void { cache.clear(); },
    };
  }, { blocked: { kind: "question", message: "Select a Loom branch" } });
}
