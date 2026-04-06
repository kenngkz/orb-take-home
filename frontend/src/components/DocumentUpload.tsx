import { Loader2, Upload } from "lucide-react";
import { type DragEvent, useCallback, useRef, useState } from "react";

interface DocumentUploadProps {
	onUpload: (file: File) => Promise<void> | void;
	uploading?: boolean;
}

export function DocumentUpload({
	onUpload,
	uploading = false,
}: DocumentUploadProps) {
	const [dragOver, setDragOver] = useState(false);
	const fileInputRef = useRef<HTMLInputElement>(null);

	const handleDragOver = useCallback((e: DragEvent) => {
		e.preventDefault();
		setDragOver(true);
	}, []);

	const handleDragLeave = useCallback((e: DragEvent) => {
		e.preventDefault();
		setDragOver(false);
	}, []);

	const handleDrop = useCallback(
		async (e: DragEvent) => {
			e.preventDefault();
			setDragOver(false);
			const pdfFiles = Array.from(e.dataTransfer.files).filter(
				(f) => f.type === "application/pdf",
			);
			for (const file of pdfFiles) {
				await onUpload(file);
			}
		},
		[onUpload],
	);

	const handleClick = useCallback(() => {
		fileInputRef.current?.click();
	}, []);

	const handleFileChange = useCallback(
		async (e: React.ChangeEvent<HTMLInputElement>) => {
			const files = e.target.files;
			if (files) {
				for (const file of Array.from(files)) {
					await onUpload(file);
				}
			}
			if (fileInputRef.current) {
				fileInputRef.current.value = "";
			}
		},
		[onUpload],
	);

	return (
		<button
			type="button"
			className={`w-full max-w-md cursor-pointer rounded-xl border-2 border-dashed px-8 py-10 text-center transition-colors ${
				dragOver
					? "border-neutral-400 bg-neutral-100"
					: "border-neutral-200 bg-white hover:border-neutral-300 hover:bg-neutral-50"
			}`}
			onDragOver={handleDragOver}
			onDragLeave={handleDragLeave}
			onDrop={handleDrop}
			onClick={handleClick}
		>
			<input
				ref={fileInputRef}
				type="file"
				accept=".pdf"
				multiple
				className="hidden"
				onChange={handleFileChange}
			/>

			{uploading ? (
				<div className="flex flex-col items-center">
					<Loader2 className="mb-3 h-10 w-10 animate-spin text-neutral-400" />
					<p className="text-sm font-medium text-neutral-600">
						Uploading document...
					</p>
				</div>
			) : (
				<div className="flex flex-col items-center">
					<Upload className="mb-3 h-10 w-10 text-neutral-400" />
					<p className="text-sm font-medium text-neutral-600">
						Upload PDF documents
					</p>
					<p className="mt-1 text-xs text-neutral-400">
						Click or drag and drop
					</p>
				</div>
			)}
		</button>
	);
}
