/**
 * /loom: compare sampled continuations in the native Pi session tree.
 * Concept: Janus's Loom. Ported from sigilmakes/pi-loom (MIT, ca741273),
 * targeting Sinnix's pinned @earendil-works/pi 1.5.2 rather than the
 * incompatible older @mariozechner/pi module.
 *
 * The single private Pi seam, branch/appendMessage, stays isolated below
 * and is tested against the actual pinned SessionManager. Provider calls
 * go through ModelRegistry, never an unconfigured raw API-key client.
 */
import type { AssistantMessage, Model, Api, Message, ThinkingLevel } from "@earendil-works/pi-ai";
import type { ExtensionAPI, ExtensionCommandContext, SessionManager } from "@earendil-works/pi-coding-agent";
import { convertToLlm } from "@earendil-works/pi-coding-agent";
import { chooseLoomBranch } from "../lib/loom-picker.ts";

const MAX = 6;
const DEFAULT = 3;
const TOKENS = 1200;

export interface LoomCandidate {
  model: Model<Api>;
  response: AssistantMessage;
  text: string;
}
export type LoomRequest =
  | { kind: "single"; count: number; prompt: string }
  | { kind: "models"; specs: string[]; prompt: string };

export function parseLoomRequest(raw: string): LoomRequest {
  let s = raw.trim();
  if (!s) throw new Error("Usage: /loom [2-6] <prompt> or /loom --models [model1,model2] <prompt>");
  if (s.startsWith("--models")) {
    s = s.slice(8).trim();
    if (!s) throw new Error("Supply a prompt after --models.");
    const token = s.split(/\s+/)[0];
    const specs = token.includes(",") ? token.split(",").map(x => x.trim()).filter(Boolean) : [];
    if (specs.length) s = s.slice(token.length).trim();
    if (specs.length > MAX) throw new Error("At most " + MAX + " models.");
    if (!s) throw new Error("Supply a prompt after the model selectors.");
    return { kind: "models", specs, prompt: s };
  }
  let count = DEFAULT;
  const match = s.match(/^(\d+)\s+([\s\S]+)$/);
  if (match) { count = Number(match[1]); s = match[2].trim(); }
  if (!Number.isInteger(count) || count < 2 || count > MAX)
    throw new Error("Loom accepts 2-" + MAX + " alternatives; no unbounded fan-out.");
  if (!s) throw new Error("Supply a prompt.");
  return { kind: "single", count, prompt: s };
}

export function isPlanModel(ctx: ExtensionCommandContext, m: Model<Api>): boolean {
  // Our live OpenAI OAuth login is a ChatGPT subscription. Anthropic direct
  // requests here could bypass the installed Claude Code plan overage guard.
  return m.provider === "openai" && ctx.modelRegistry.isUsingOAuth(m);
}

export function loomModels(ctx: ExtensionCommandContext, request: LoomRequest): Model<Api>[] {
  if (request.kind === "single") {
    if (!ctx.model || !isPlanModel(ctx, ctx.model)) {
      throw new Error("Loom requires a ChatGPT OAuth model; metered and other providers are disabled here.");
    }
    return Array.from({ length: request.count }, () => ctx.model as Model<Api>);
  }
  const all = ctx.modelRegistry.getAvailable().filter(m => isPlanModel(ctx, m));
  if (request.specs.length) {
    const picked: Model<Api>[] = [];
    for (const spec of request.specs) {
      const hits = all.filter(m => (m.id + " " + m.name).toLowerCase().includes(spec.toLowerCase()));
      if (hits.length !== 1) throw new Error("Model selector " + JSON.stringify(spec) + " matched " + hits.length + " plan models; make it specific.");
      if (!picked.some(m => m.id === hits[0].id)) picked.push(hits[0]);
    }
    if (picked.length < 2) throw new Error("Choose at least two distinct ChatGPT OAuth models.");
    return picked;
  }
  const sorted = ctx.model && isPlanModel(ctx, ctx.model)
    ? [ctx.model, ...all.filter(m => m.id !== ctx.model!.id)] : all;
  if (sorted.length < 2) throw new Error("Need at least two available ChatGPT OAuth models.");
  return sorted.slice(0, DEFAULT);
}

function usedOverage(response: AssistantMessage): boolean {
  return (response.diagnostics ?? []).some(d => {
    if (d.type !== "claude-code.rate-limit") return false;
    const detail = (d as { details?: Record<string, unknown> }).details;
    return detail?.rateLimitType === "overage" || detail?.overageInUse === true || detail?.isUsingOverage === true;
  });
}

export async function collectLoomCandidates(
  ctx: ExtensionCommandContext, pi: ExtensionAPI, request: LoomRequest,
  models: Model<Api>[], signal: AbortSignal,
  progress?: (received: number, total: number) => void,
): Promise<{ candidates: LoomCandidate[]; failures: string[] }> {
  // buildSessionContext honors compaction, branch summaries and context edits.
  const messages = convertToLlm(ctx.sessionManager.buildSessionContext().messages);
  const context = {
    systemPrompt: ctx.getSystemPrompt(),
    messages: messages.concat([{ role: "user", content: [{ type: "text", text: request.prompt }], timestamp: Date.now() }]),
    tools: [],
  } as const;
  const level = pi.getThinkingLevel();
  const reasoning = level === "off" ? undefined : level as ThinkingLevel;
  const candidates: LoomCandidate[] = [], failures: string[] = [];
  for (const [index, model] of models.entries()) {
    if (signal.aborted) break;
    try {
      // Native credential, model policy, and auth refresh. No API keys exported.
      const result = ctx.modelRegistry.streamSimple(model, context, {
        signal, reasoning, maxTokens: TOKENS, maxRetries: 0, toolChoice: "none",
      });
      const response = await result.result();
      if (usedOverage(response)) throw new Error("Provider used usage credits; stopping Loom.");
      if (response.stopReason !== "stop" && response.stopReason !== "length")
        throw new Error("Model stopped with " + response.stopReason + (response.errorMessage ? ": " + response.errorMessage : ""));
      if (response.content.some(part => part.type === "toolCall")) throw new Error("Unexpected tool call.");
      const text = response.content.filter(part => part.type === "text").map(part => part.text).join("\n").trim();
      if (!text) throw new Error("Empty text.");
      candidates.push({ model, response, text });
    } catch (error) {
      if (signal.aborted) break;
      const message = error instanceof Error ? error.message : String(error);
      failures.push(String(index + 1) + " (" + model.id + "): " + message);
      if (/usage credits|overage/i.test(message)) break;
    }
    progress?.(index + 1, models.length);
  }
  return { candidates, failures };
}

/** One non-public seam, tested with Pi's actual in-memory SessionManager. */
export function insertLoomBranches(
  session: ExtensionCommandContext["sessionManager"], prompt: string,
  candidates: LoomCandidate[], selected: number,
): { branchPoint: string; selectedLeaf: string; leaves: string[] } {
  if (!Number.isInteger(selected) || selected < 0 || selected >= candidates.length)
    throw new Error("Invalid selection.");
  const sm = session as unknown as SessionManager;
  if (typeof sm.branch !== "function" || typeof sm.appendMessage !== "function")
    throw new Error("Pinned Pi session insertion contract is unavailable.");
  const branchPoint = sm.getLeafId();
  if (!branchPoint) throw new Error("Send one ordinary message before looming a new branch.");
  const leaves = new Array<string>(candidates.length);
  // Alternatives first, chosen last. No branch mutation before selection.
  for (const i of [...candidates.keys()].filter(i => i !== selected).concat(selected)) {
    sm.branch(branchPoint);
    sm.appendMessage({ role: "user", content: [{ type: "text", text: prompt }], timestamp: Date.now() } as Message);
    leaves[i] = sm.appendMessage(candidates[i].response);
  }
  return { branchPoint, selectedLeaf: leaves[selected], leaves };
}

export default function loom(pi: ExtensionAPI) {
  pi.registerCommand("loom", {
    description: "Sample 2-6 ChatGPT-plan continuations; select one and retain all in /tree",
    handler: async (raw, ctx) => {
      if (!ctx.hasUI) { ctx.ui.notify("Loom needs TUI or dialog-capable RPC.", "error"); return; }
      let request: LoomRequest, models: Model<Api>[];
      try {
        request = parseLoomRequest(raw);
        models = loomModels(ctx, request);
        if (!ctx.sessionManager.getLeafId()) throw new Error("First send one ordinary Pi message.");
      } catch (error) { ctx.ui.notify(error instanceof Error ? error.message : String(error), "error"); return; }

      const controller = new AbortController();
      let completed = 0;
      let outcome: { candidates: LoomCandidate[]; failures: string[] } | null;
      if (ctx.mode === "tui") {
        outcome = await ctx.ui.custom((tui, theme, _keys, done) => {
          let closed = false;
          const finish = (value: typeof outcome) => { if (!closed) { closed = true; done(value); } };
          collectLoomCandidates(ctx, pi, request, models, controller.signal, n => {
            completed = n; tui.requestRender?.();
          }).then(finish, error => {
            ctx.ui.notify("Loom error: " + (error instanceof Error ? error.message : String(error)), "error");
            finish(null);
          });
          return {
            render(width: number) {
              return [
                theme.fg("accent", "Loom · sampling " + models.length + " alternatives"),
                String(completed) + "/" + models.length + " · " + request.prompt.slice(0, Math.max(0, width - 10)),
                theme.fg("muted", "Esc cancels without editing the session"),
              ];
            },
            handleInput(data: string) {
              if (data === "\u001b" || data === "escape") { controller.abort(); finish(null); }
            },
            invalidate() {},
          };
        });
      } else {
        ctx.ui.notify("Loom: sampling " + models.length + " plan-backed continuations", "info");
        outcome = await collectLoomCandidates(ctx, pi, request, models, controller.signal).catch(error => {
          ctx.ui.notify(String(error), "error"); return null;
        });
      }
      if (!outcome) return;
      if (outcome.failures.length) ctx.ui.notify(outcome.failures.join("; ").slice(0, 900), "warning");
      if (!outcome.candidates.length) return;
      const selected = await chooseLoomBranch(ctx, request.prompt, outcome.candidates);
      if (selected === null) return;
      try {
        const { branchPoint, selectedLeaf } = insertLoomBranches(
          ctx.sessionManager, request.prompt, outcome.candidates, selected);
        const away = await ctx.navigateTree(branchPoint, { summarize: false });
        const back = away.cancelled ? { cancelled: true } : await ctx.navigateTree(selectedLeaf, { summarize: false });
        if (away.cancelled || back.cancelled) throw new Error("Navigation cancelled; use /tree to recover the selected branch.");
        const chosenModel = outcome.candidates[selected].model;
        if (ctx.model && chosenModel.id !== ctx.model.id && !await pi.setModel(chosenModel))
          ctx.ui.notify("Branch retained; model switch failed, continuing with current model.", "warning");
        ctx.ui.notify("Loom: " + outcome.candidates.length + " branches retained. Open /tree to revisit.", "info");
      } catch (error) {
        ctx.ui.notify("Loom branches retained but view refresh failed: " + String(error), "error");
      }
    },
  });
}
