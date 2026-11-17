/** One question, answered through either the terminal or an RPC front end.
 * Recommendations belong to decisions, not neutral elicitation. Omit choices
 * for a direct text answer; a dismissal never becomes a default choice.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { askChoice, canAsk } from "../lib/choice.ts";

export const askParameters = Type.Object({
	question: Type.String({ minLength: 1, description: "One question the operator can answer in their own terms." }),
	why: Type.Optional(Type.String({ description: "Relevant context, when needed to understand the question." })),
	recommendation: Type.Optional(Type.String({ description: "A recommendation for an actual decision. Omit for neutral inquiry, beliefs, learning checks and blind comparisons." })),
	choices: Type.Optional(Type.Array(
		Type.Object({
			label: Type.String({ minLength: 1, description: "A short, distinguishable choice." }),
			consequence: Type.Optional(Type.String({ description: "What follows from picking it." })),
		}),
		{ minItems: 2, maxItems: 9, description: "Optional choices, each with a digit key. Omit for a direct free-text answer. Text and dismissal remain available with choices." },
	)),
	recommended: Type.Optional(Type.Integer({ minimum: 1, maximum: 9, description: "One-based choice number, only when a recommendation and choices are supplied." })),
});

export const askResult = Type.Object({
	answered: Type.Boolean({ description: "False when the operator dismissed the question or supplied no answer." }),
	choice: Type.Optional(Type.Integer({ description: "One-based number of the picked choice." })),
	label: Type.Optional(Type.String({ description: "Label of the picked choice." })),
	text: Type.Optional(Type.String({ description: "The operator's typed answer, without rewriting." })),
});

export default function ask(pi: ExtensionAPI) {
	pi.registerTool({
		name: "ask_operator",
		label: "Ask the operator",
		description: "Ask one question and wait for the answer. Omit choices for direct text, or supply two to nine choices with consequences. Add a recommendation only for a decision, not neutral elicitation. The operator may type another answer or dismiss; no answer is inferred from dismissal.",
		promptSnippet: "Ask one neutral question or decision, receiving the answer as data",
		promptGuidelines: [
			"Ask one question per call. Do not preselect a personal belief or supply a recommendation when eliciting the operator's own view.",
		],
		parameters: askParameters,
		outputSchema: askResult,
		executionMode: "sequential",
		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			if (!canAsk(ctx)) throw new Error("ask_operator needs an operator: this run has no way to show a question.");
			const choices = params.choices ?? [];
			if (params.recommended !== undefined && (!params.recommendation || params.recommended > choices.length)) {
				throw new Error("A recommended choice needs a recommendation and an existing choice number.");
			}
			const body = [];
			if (params.why) body.push(params.why);
			if (params.recommendation) body.push(`Recommendation: ${params.recommendation}`);
			const answer = await askChoice(ctx, {
				title: params.question,
				body,
				choices: choices.map((choice, index) => ({
					key: String(index + 1),
					label: index + 1 === params.recommended ? `${choice.label} (recommended)` : choice.label,
					detail: choice.consequence ? [choice.consequence] : undefined,
				})),
				allowText: true,
			});
			const result = answer.kind === "choice"
				? { answered: true, choice: Number(answer.key), label: choices[Number(answer.key) - 1].label }
				: answer.kind === "text" ? { answered: true, text: answer.text } : { answered: false };
			const summary = answer.kind === "choice"
				? `The operator chose ${result.choice}: ${result.label}`
				: answer.kind === "text" ? `The operator answered: ${answer.text}` : "The operator dismissed the question without answering.";
			return { content: [{ type: "text", text: summary }], details: { question: params, result }, structuredContent: result };
		},
	});
}
