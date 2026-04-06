import { ChevronLeft, ChevronRight, FileText, Loader2, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Document as PDFDocument, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { getDocumentUrl } from "../lib/api";
import type { Document } from "../types";
import { Button } from "./ui/button";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
	"pdfjs-dist/build/pdf.worker.min.mjs",
	import.meta.url,
).toString();

const MIN_WIDTH = 280;
const MAX_WIDTH = 700;
const DEFAULT_WIDTH = 400;

interface DocumentViewerProps {
	documents: Document[];
	onRemove?: (documentId: string) => void;
	activeDocumentId?: string | null;
	onSelectDocument?: (id: string) => void;
}

export function DocumentViewer({
	documents,
	onRemove,
	activeDocumentId,
	onSelectDocument,
}: DocumentViewerProps) {
	const [numPages, setNumPages] = useState<number>(0);
	const [currentPage, setCurrentPage] = useState(1);
	const [pdfLoading, setPdfLoading] = useState(true);
	const [pdfError, setPdfError] = useState<string | null>(null);
	const [width, setWidth] = useState(DEFAULT_WIDTH);
	const [dragging, setDragging] = useState(false);
	const containerRef = useRef<HTMLDivElement>(null);

	const activeDocument =
		documents.find((d) => d.id === activeDocumentId) ?? documents[0] ?? null;

	useEffect(() => {
		const first = documents[0];
		if (first && !activeDocumentId) {
			onSelectDocument?.(first.id);
		}
	}, [documents, activeDocumentId, onSelectDocument]);

	const prevDocRef = useRef(activeDocumentId);
	if (prevDocRef.current !== activeDocumentId) {
		prevDocRef.current = activeDocumentId;
		setCurrentPage(1);
		setNumPages(0);
		setPdfLoading(true);
		setPdfError(null);
	}

	const handleMouseDown = useCallback(
		(e: React.MouseEvent) => {
			e.preventDefault();
			setDragging(true);

			const startX = e.clientX;
			const startWidth = width;

			const handleMouseMove = (moveEvent: MouseEvent) => {
				const delta = startX - moveEvent.clientX;
				const newWidth = Math.min(
					MAX_WIDTH,
					Math.max(MIN_WIDTH, startWidth + delta),
				);
				setWidth(newWidth);
			};

			const handleMouseUp = () => {
				setDragging(false);
				window.removeEventListener("mousemove", handleMouseMove);
				window.removeEventListener("mouseup", handleMouseUp);
			};

			window.addEventListener("mousemove", handleMouseMove);
			window.addEventListener("mouseup", handleMouseUp);
		},
		[width],
	);

	const pdfPageWidth = width - 48;

	if (documents.length === 0) {
		return (
			<div
				style={{ width }}
				className="flex h-full flex-shrink-0 flex-col items-center justify-center border-l border-neutral-200 bg-neutral-50"
			>
				<FileText className="mb-3 h-10 w-10 text-neutral-300" />
				<p className="text-sm text-neutral-400">No document uploaded</p>
			</div>
		);
	}

	const pdfUrl = activeDocument ? getDocumentUrl(activeDocument.id) : null;

	return (
		<div
			ref={containerRef}
			style={{ width }}
			className="relative flex h-full flex-shrink-0 flex-col border-l border-neutral-200 bg-white"
		>
			{/* Resize handle */}
			<div
				className={`absolute top-0 left-0 z-10 h-full w-1.5 cursor-col-resize transition-colors hover:bg-neutral-300 ${
					dragging ? "bg-neutral-400" : ""
				}`}
				onMouseDown={handleMouseDown}
			/>

			{/* Document list */}
			{documents.length > 1 && (
				<div className="flex gap-1 overflow-x-auto border-b border-neutral-100 px-4 py-2">
					{documents.map((doc) => (
						<button
							key={doc.id}
							type="button"
							className={`group flex flex-shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs transition-colors ${
								doc.id === activeDocument?.id
									? "bg-neutral-100 font-medium text-neutral-800"
									: "text-neutral-500 hover:bg-neutral-50 hover:text-neutral-700"
							}`}
							onClick={() => onSelectDocument?.(doc.id)}
						>
							<FileText className="h-3 w-3 flex-shrink-0" />
							<span className="max-w-[120px] truncate">{doc.filename}</span>
							{onRemove && (
								<button
									type="button"
									className="ml-0.5 rounded p-0.5 opacity-0 transition-opacity hover:bg-neutral-200 group-hover:opacity-100"
									onClick={(e) => {
										e.stopPropagation();
										onRemove(doc.id);
									}}
								>
									<X className="h-3 w-3" />
								</button>
							)}
						</button>
					))}
				</div>
			)}

			{/* Header */}
			{activeDocument && (
				<div className="flex items-center justify-between border-b border-neutral-100 px-4 py-3">
					<div className="min-w-0">
						<p className="truncate text-sm font-medium text-neutral-800">
							{activeDocument.filename}
						</p>
						<p className="text-xs text-neutral-400">
							{activeDocument.page_count} page
							{activeDocument.page_count !== 1 ? "s" : ""}
						</p>
					</div>
					{documents.length === 1 && onRemove && (
						<Button
							variant="ghost"
							size="icon"
							className="h-7 w-7 text-neutral-400 hover:text-neutral-600"
							onClick={() => onRemove(activeDocument.id)}
						>
							<X className="h-4 w-4" />
						</Button>
					)}
				</div>
			)}

			{/* PDF content */}
			<div className="flex-1 overflow-y-auto p-4">
				{pdfError && (
					<div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">
						{pdfError}
					</div>
				)}

				{pdfUrl && (
					<PDFDocument
						file={pdfUrl}
						onLoadSuccess={({ numPages: pages }) => {
							setNumPages(pages);
							setPdfLoading(false);
							setPdfError(null);
						}}
						onLoadError={(error) => {
							setPdfError(`Failed to load PDF: ${error.message}`);
							setPdfLoading(false);
						}}
						loading={
							<div className="flex items-center justify-center py-12">
								<Loader2 className="h-6 w-6 animate-spin text-neutral-400" />
							</div>
						}
					>
						{!pdfLoading && !pdfError && (
							<Page
								pageNumber={currentPage}
								width={pdfPageWidth}
								loading={
									<div className="flex items-center justify-center py-12">
										<Loader2 className="h-5 w-5 animate-spin text-neutral-300" />
									</div>
								}
							/>
						)}
					</PDFDocument>
				)}
			</div>

			{/* Page navigation */}
			{numPages > 0 && (
				<div className="flex items-center justify-center gap-3 border-t border-neutral-100 px-4 py-2.5">
					<Button
						variant="ghost"
						size="icon"
						className="h-7 w-7"
						disabled={currentPage <= 1}
						onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
					>
						<ChevronLeft className="h-4 w-4" />
					</Button>
					<span className="text-xs text-neutral-500">
						Page {currentPage} of {numPages}
					</span>
					<Button
						variant="ghost"
						size="icon"
						className="h-7 w-7"
						disabled={currentPage >= numPages}
						onClick={() => setCurrentPage((p) => Math.min(numPages, p + 1))}
					>
						<ChevronRight className="h-4 w-4" />
					</Button>
				</div>
			)}
		</div>
	);
}
