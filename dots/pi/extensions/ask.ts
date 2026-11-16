/**
 * ask_operator: the model asks the operator one question in a fixed shape
 * and receives the answer as data.
 *
 * The shape is the point. A question states what is being decided, why it
 * matters, what the model recommends, and choices that each take one key.
 * The operator can also type an answer or dismiss the question.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { askChoice, canAsk } from "../lib/choice.ts";

export const askParameters = Type.Object({
	deciding: Type.String({ description: "What is being decided, as one question the operator can answer." }),
	why: Type.String({ description: "Why it matters: what changes depending on the answer." }),
	recommendation: Type.String({ description: "The choice you recommend and the reason, in a sentence or two." }),
	choices: Type.Array(
		Type.Object({
			label: Type.String({ description: "The choice, short enough to read at a glance." }),
			consequence: Type.Optional(Type.String({ description: "What follows from picking it." })),
		}),
		{ minItems: 2, maxItems: 9, description: "The choices. Each gets a digit key in the order given." },
	),
	recommended: Type.Optional(
		Type.Integer({ minimum: 1, maximum: 9, description: "Number of the recommended choice, counting from 1." }),
	),
});

export const askResult = Type.Object({
	answered: Type.Boolean({ description: "False when the operator dismissed the question." }),
	choice: Type.Optional(Type.Integer({ description: "Number of the picked choice, counting from 1." })),
	label: Type.Optional(Type.String({ description: "Label of the picked choice." })),
	text: Type.Optional(Type.String({ description: "The operator's typed answer, when they typed one." })),
});

export default function ask(pi: ExtensionAPI) {
	pi.registerTool({
		name: "ask_operator",
		label: "Ask the operator",
		description:
			"Ask the operator one question and wait for the answer. State what is being decided, why it matters, " +
			"your recommendation, and two to nine choices; the operator picks one with a single key, types an " +
			"answer, or dismisses the question. Returns the answer as data.",
		promptSnippet: "Ask the operator one structured question and get the answer as data",
		promptGuidelines: [
			"Use ask_operator when a decision belongs to the operator; ask one question per call instead of listing questions in prose.",
		],
		parameters: askParameters,
		outputSchema: askResult,
		executionMode: "sequential",

		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			if (!canAsk(ctx)) {
				throw new Error("ask_operator needs an operator: this run has no way to show a question.");
			}
			const answer = await askChoice(ctx, {
				title: params.deciding,
				body: [`Why it matters: ${params.why}`, `Recommendation: ${params.recommendation}`],
				choices: params.choices.map((choice, index) => ({
					key: String(index + 1),
					label: index + 1 === params.recommended ? `${choice.label} (recommended)` : choice.label,
					detail: choice.consequence ? [choice.consequence] : undefined,
				})),
				allowText: true,
			});

			const result =
				answer.kind === "choice"
					? { answered: true, choice: Number(answer.key), label: params.choices[Number(answer.key) - 1].label }
					: answer.kind === "text"
						? { answered: true, text: answer.text }
						: { answered: false };
			const summary =
				answer.kind === "choice"
					? `The operator chose ${result.choice}: ${result.label}`
					: answer.kind === "text"
						? `The operator answered: ${answer.text}`
						: "The operator dismissed the question without answering.";
			return {
				content: [{ type: "text", text: summary }],
				details: { question: params, result },
				structuredContent: result,
			};
		},
	});
}
