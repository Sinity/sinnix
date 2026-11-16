/**
 * Stops a Claude Code turn that was charged to usage credits.
 *
 * Claude models reach pi through the Claude Code provider, which runs on the
 * Claude plan. Anthropic can instead charge a request to pay-as-you-go usage
 * credits, and the provider's own check misses the case where the request is
 * allowed but served from credits. The provider attaches the rate-limit
 * status to each reply; when that status says credits were used, this handler
 * stops the run and says so, so one charged request does not become many.
 *
 * With usage credits switched off for the account such a request fails
 * instead of being charged, and this never fires.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const PROVIDER = "claude-code";
const RATE_LIMIT_DIAGNOSTIC = "claude-code.rate-limit";

export function chargedToUsageCredits(message: unknown): boolean {
	const reply = message as { role?: string; provider?: string; diagnostics?: Array<{ type?: string; details?: any }> };
	if (reply?.role !== "assistant" || reply.provider !== PROVIDER) return false;
	return (reply.diagnostics ?? []).some(
		(diagnostic) =>
			diagnostic.type === RATE_LIMIT_DIAGNOSTIC &&
			(diagnostic.details?.rateLimitType === "overage" ||
				diagnostic.details?.overageInUse === true ||
				diagnostic.details?.isUsingOverage === true),
	);
}

export default function planBilling(pi: ExtensionAPI) {
	pi.on("message_end", async (event, ctx) => {
		if (!chargedToUsageCredits(event.message)) return;
		ctx.abort();
		ctx.ui.notify(
			"Stopped: Anthropic charged the last Claude reply to usage credits, not the Claude plan. " +
				"Switch usage credits off at claude.ai/settings/usage or use another model before continuing.",
			"error",
		);
	});
}
