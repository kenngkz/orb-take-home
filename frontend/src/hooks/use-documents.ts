import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../lib/api";
import type { Document } from "../types";

export function useDocuments(conversationId: string | null) {
	const [documents, setDocuments] = useState<Document[]>([]);
	const [uploading, setUploading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [activeDocumentId, setActiveDocumentId] = useState<string | null>(null);

	const activeDocument =
		documents.find((d) => d.id === activeDocumentId) ?? documents[0] ?? null;

	const activeDocIdRef = useRef(activeDocumentId);
	activeDocIdRef.current = activeDocumentId;

	const refresh = useCallback(async () => {
		if (!conversationId) {
			setDocuments([]);
			setActiveDocumentId(null);
			return;
		}
		try {
			setError(null);
			const docs = await api.fetchDocuments(conversationId);
			setDocuments(docs);

			const currentId = activeDocIdRef.current;
			if (currentId === null || !docs.some((d) => d.id === currentId)) {
				setActiveDocumentId(docs[0]?.id ?? null);
			}
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to load documents");
		}
	}, [conversationId]);

	useEffect(() => {
		refresh();
	}, [refresh]);

	const upload = useCallback(
		async (file: File) => {
			if (!conversationId) return null;
			try {
				setUploading(true);
				setError(null);
				const doc = await api.uploadDocument(conversationId, file);
				setDocuments((prev) => [...prev, doc]);

				setActiveDocumentId((current) => current ?? doc.id);
				return doc;
			} catch (err) {
				setError(
					err instanceof Error ? err.message : "Failed to upload document",
				);
				return null;
			} finally {
				setUploading(false);
			}
		},
		[conversationId],
	);

	const remove = useCallback(async (documentId: string) => {
		try {
			setError(null);
			await api.deleteDocument(documentId);
			setDocuments((prev) => prev.filter((d) => d.id !== documentId));
			setActiveDocumentId((current) =>
				current === documentId ? null : current,
			);
		} catch (err) {
			setError(
				err instanceof Error ? err.message : "Failed to delete document",
			);
		}
	}, []);

	const selectDocument = useCallback((id: string | null) => {
		setActiveDocumentId(id);
	}, []);

	return {
		documents,
		activeDocument,
		activeDocumentId,
		selectDocument,
		uploading,
		error,
		upload,
		remove,
		refresh,
	};
}
