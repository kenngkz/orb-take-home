import { useCallback, useEffect, useState } from "react";
import * as api from "../lib/api";
import type { Document } from "../types";

export function useDocuments(conversationId: string | null) {
	const [documents, setDocuments] = useState<Document[]>([]);
	const [uploading, setUploading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const refresh = useCallback(async () => {
		if (!conversationId) {
			setDocuments([]);
			return;
		}
		try {
			setError(null);
			const docs = await api.fetchDocuments(conversationId);
			setDocuments(docs);
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
		} catch (err) {
			setError(
				err instanceof Error ? err.message : "Failed to delete document",
			);
		}
	}, []);

	return {
		documents,
		uploading,
		error,
		upload,
		remove,
		refresh,
	};
}
