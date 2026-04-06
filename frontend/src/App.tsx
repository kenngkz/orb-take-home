import { useCallback, useState } from "react";
import { ChatSidebar } from "./components/ChatSidebar";
import { ChatWindow } from "./components/ChatWindow";
import { DocumentViewer } from "./components/DocumentViewer";
import { TooltipProvider } from "./components/ui/tooltip";
import { useConversations } from "./hooks/use-conversations";
import { useDocuments } from "./hooks/use-documents";
import { useMessages } from "./hooks/use-messages";

export default function App() {
	const {
		conversations,
		selectedId,
		loading: conversationsLoading,
		create,
		select,
		remove,
		refresh: refreshConversations,
	} = useConversations();

	const {
		messages,
		loading: messagesLoading,
		error: messagesError,
		streaming,
		streamingContent,
		send,
	} = useMessages(selectedId);

	const {
		documents,
		upload,
		remove: removeDocument,
		refresh: refreshDocuments,
	} = useDocuments(selectedId);

	const [activeDocumentId, setActiveDocumentId] = useState<string | null>(null);

	const handleSend = useCallback(
		async (content: string) => {
			await send(content);
			refreshConversations();
		},
		[send, refreshConversations],
	);

	const handleUpload = useCallback(
		async (file: File) => {
			const doc = await upload(file);
			if (doc) {
				refreshDocuments();
				refreshConversations();
			}
		},
		[upload, refreshDocuments, refreshConversations],
	);

	const handleRemoveDocument = useCallback(
		async (documentId: string) => {
			await removeDocument(documentId);
			refreshConversations();
		},
		[removeDocument, refreshConversations],
	);

	const handleCreate = useCallback(async () => {
		await create();
	}, [create]);

	return (
		<TooltipProvider delayDuration={200}>
			<div className="flex h-screen bg-neutral-50">
				<ChatSidebar
					conversations={conversations}
					selectedId={selectedId}
					loading={conversationsLoading}
					onSelect={select}
					onCreate={handleCreate}
					onDelete={remove}
				/>

				<ChatWindow
					messages={messages}
					loading={messagesLoading}
					error={messagesError}
					streaming={streaming}
					streamingContent={streamingContent}
					conversationId={selectedId}
					onSend={handleSend}
					onUpload={handleUpload}
				/>

				<DocumentViewer
					documents={documents}
					onRemove={handleRemoveDocument}
					activeDocumentId={activeDocumentId}
					onSelectDocument={setActiveDocumentId}
				/>
			</div>
		</TooltipProvider>
	);
}
