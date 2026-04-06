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
		activeDocument,
		activeDocumentId,
		selectDocument,
		upload,
		remove: removeDocument,
		refresh: refreshDocuments,
	} = useDocuments(selectedId);

	const [targetPage, setTargetPage] = useState<number | null>(null);

	const handleCitationClick = useCallback(
		(documentId: string, pageNumber: number) => {
			selectDocument(documentId);
			// Reset then set to ensure useEffect fires even for the same page
			setTargetPage(null);
			queueMicrotask(() => setTargetPage(pageNumber));
		},
		[selectDocument],
	);

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

	return (
		<TooltipProvider delayDuration={200}>
			<div className="flex h-screen bg-neutral-50">
				<ChatSidebar
					conversations={conversations}
					selectedId={selectedId}
					loading={conversationsLoading}
					onSelect={select}
					onCreate={create}
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
					onCitationClick={handleCitationClick}
				/>

				{selectedId && (
					<DocumentViewer
						documents={documents}
						activeDocument={activeDocument}
						onRemove={handleRemoveDocument}
						activeDocumentId={activeDocumentId}
						onSelectDocument={selectDocument}
						targetPage={targetPage}
					/>
				)}
			</div>
		</TooltipProvider>
	);
}
