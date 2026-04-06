import { motion } from "framer-motion";
import { Bot, FileText } from "lucide-react";
import type { MouseEvent } from "react";
import { useCallback, useEffect, useRef } from "react";
import { Streamdown } from "streamdown";
import "streamdown/styles.css";
import type { Message } from "../types";

const CITE_MARKER_RE = /\[(\d+)\]/g;

/**
 * Walk the rendered DOM and replace text `[N]` with clickable button elements.
 * Runs after Streamdown renders so we bypass its HTML sanitisation.
 */
function replaceCiteMarkersInDom(
	container: HTMLElement,
	citationCount: number,
) {
	const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);

	const toReplace: { node: Text; text: string }[] = [];
	let textNode = walker.nextNode() as Text | null;
	while (textNode) {
		if (textNode.textContent && CITE_MARKER_RE.test(textNode.textContent)) {
			toReplace.push({ node: textNode, text: textNode.textContent });
		}
		CITE_MARKER_RE.lastIndex = 0;
		textNode = walker.nextNode() as Text | null;
	}

	for (const { node, text } of toReplace) {
		const frag = document.createDocumentFragment();
		let lastIdx = 0;

		for (const match of text.matchAll(CITE_MARKER_RE)) {
			const idx = match.index ?? 0;
			const num = Number.parseInt(match[1] ?? "0", 10);
			const citeIdx = num - 1;

			if (idx > lastIdx) {
				frag.appendChild(document.createTextNode(text.slice(lastIdx, idx)));
			}

			if (citeIdx >= 0 && citeIdx < citationCount) {
				const btn = document.createElement("button");
				btn.dataset.cite = String(citeIdx);
				btn.textContent = String(num);
				btn.style.cssText =
					"display:inline-flex;align-items:center;justify-content:center;" +
					"min-width:1.4em;height:1.4em;padding:0 4px;border-radius:4px;" +
					"background:#dbeafe;color:#1d4ed8;font-size:0.8em;font-weight:600;" +
					"cursor:pointer;border:none;vertical-align:middle;line-height:1;margin:0 2px";
				frag.appendChild(btn);
			} else {
				frag.appendChild(document.createTextNode(match[0]));
			}

			lastIdx = idx + match[0].length;
		}

		if (lastIdx < text.length) {
			frag.appendChild(document.createTextNode(text.slice(lastIdx)));
		}

		node.parentNode?.replaceChild(frag, node);
	}
}

interface MessageBubbleProps {
	message: Message;
	onCitationClick?: (documentId: string, pageNumber: number) => void;
}

export function MessageBubble({
	message,
	onCitationClick,
}: MessageBubbleProps) {
	const proseRef = useRef<HTMLDivElement>(null);

	const handleProseClick = useCallback(
		(e: MouseEvent<HTMLDivElement>) => {
			const target = e.target as HTMLElement;
			const citeIndex = target.dataset.cite;
			if (citeIndex != null && message.citations) {
				const index = Number.parseInt(citeIndex, 10);
				const citation = message.citations[index];
				if (citation) {
					onCitationClick?.(citation.document_id, citation.page_number);
				}
			}
		},
		[message.citations, onCitationClick],
	);

	// Post-process DOM to replace [N] text with clickable buttons
	useEffect(() => {
		if (proseRef.current && message.citations?.length) {
			replaceCiteMarkersInDom(proseRef.current, message.citations.length);
		}
	}, [message.citations]);

	if (message.role === "system") {
		return (
			<motion.div
				initial={{ opacity: 0 }}
				animate={{ opacity: 1 }}
				transition={{ duration: 0.2 }}
				className="flex justify-center py-2"
			>
				<p className="text-xs text-neutral-400">{message.content}</p>
			</motion.div>
		);
	}

	if (message.role === "user") {
		return (
			<motion.div
				initial={{ opacity: 0, y: 8 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.2 }}
				className="flex justify-end py-1.5"
			>
				<div className="max-w-[75%] rounded-2xl rounded-br-md bg-neutral-100 px-4 py-2.5">
					<p className="whitespace-pre-wrap text-sm text-neutral-800">
						{message.content}
					</p>
				</div>
			</motion.div>
		);
	}

	// Assistant message
	return (
		<motion.div
			initial={{ opacity: 0, y: 8 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.2 }}
			className="flex gap-3 py-1.5"
		>
			<div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-neutral-900">
				<Bot className="h-4 w-4 text-white" />
			</div>
			<div className="min-w-0 max-w-[80%]">
				{/* biome-ignore lint/a11y/useKeyWithClickEvents: event delegation on injected citation buttons */}
				<div ref={proseRef} className="prose" onClick={handleProseClick}>
					<Streamdown>{message.content}</Streamdown>
				</div>
				{message.citations && message.citations.length > 0 && (
					<div className="mt-2 flex flex-wrap gap-1.5">
						{message.citations.map((citation, i) => (
							<button
								type="button"
								key={`${citation.document_id}-${citation.page_number}`}
								className="inline-flex items-center gap-1 rounded-md bg-neutral-100 px-2 py-1 text-xs text-neutral-600 transition-colors hover:bg-neutral-200 hover:text-neutral-800"
								onClick={() =>
									onCitationClick?.(citation.document_id, citation.page_number)
								}
							>
								<span className="inline-flex h-4 w-4 items-center justify-center rounded bg-blue-100 text-[10px] font-semibold text-blue-700">
									{i + 1}
								</span>
								<FileText className="h-3 w-3" />
								{citation.filename}, p. {citation.page_number}
							</button>
						))}
					</div>
				)}
			</div>
		</motion.div>
	);
}

interface StreamingBubbleProps {
	content: string;
}

export function StreamingBubble({ content }: StreamingBubbleProps) {
	return (
		<div className="flex gap-3 py-1.5">
			<div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-neutral-900">
				<Bot className="h-4 w-4 text-white" />
			</div>
			<div className="min-w-0 max-w-[80%]">
				{content ? (
					<div className="prose">
						<Streamdown mode="streaming">{content}</Streamdown>
					</div>
				) : (
					<div className="flex items-center gap-1 py-2">
						<span className="h-1.5 w-1.5 animate-pulse rounded-full bg-neutral-400" />
						<span
							className="h-1.5 w-1.5 animate-pulse rounded-full bg-neutral-400"
							style={{ animationDelay: "0.15s" }}
						/>
						<span
							className="h-1.5 w-1.5 animate-pulse rounded-full bg-neutral-400"
							style={{ animationDelay: "0.3s" }}
						/>
					</div>
				)}
				<span className="inline-block h-4 w-0.5 animate-pulse bg-neutral-400" />
			</div>
		</div>
	);
}
