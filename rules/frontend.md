# Frontend Patterns

React 18 + TypeScript + Vite + Tailwind CSS frontend.

## Project Structure

```
frontend/src/
├── App.tsx                # Root component, state lifted here
├── main.tsx               # Entry point
├── types.ts               # Shared TypeScript interfaces
├── components/
│   ├── ui/                # shadcn/ui primitives (Radix-based)
│   ├── ChatWindow.tsx
│   ├── ChatSidebar.tsx
│   ├── DocumentViewer.tsx
│   ├── MessageBubble.tsx
│   ├── ChatInput.tsx
│   ├── DocumentUpload.tsx
│   └── EmptyState.tsx
├── hooks/
│   ├── use-conversations.ts
│   ├── use-messages.ts
│   └── use-document.ts
└── lib/
    ├── api.ts             # Fetch-based API client
    └── utils.ts           # cn() helper
```

## State Management

No external state library. Hooks + lifted state in `App.tsx`:

- Custom hooks (`useConversations`, `useMessages`, `useDocument`) encapsulate API calls and local state
- `App.tsx` composes hooks and passes props down
- `useState` + `useCallback` for state and memoized handlers

## API Client

Plain `fetch()` in `lib/api.ts`. No axios, no tRPC. Functions return typed data:

```typescript
export async function fetchConversations(): Promise<Conversation[]> {
  const res = await fetch("/api/conversations");
  return res.json();
}
```

## Streaming

Frontend reads SSE streams from the backend:

- Uses `fetch()` with `response.body` stream
- Parses `data: {...}\n\n` events
- Updates React state on each chunk for real-time UI

## Components

- **UI primitives:** shadcn/ui (Radix UI + Tailwind), in `components/ui/`
- **Icons:** lucide-react
- **Animations:** Framer Motion
- **PDF rendering:** react-pdf + pdfjs-dist

## Types

Shared interfaces in `types.ts`. No `I` prefix:

```typescript
export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  has_document: boolean;
}
```

## Import Alias

`@/*` maps to `./src/*` (configured in `tsconfig.json`):

```typescript
import { useConversations } from "@/hooks/use-conversations";
```

## Linting & Formatting

Biome (replaces ESLint + Prettier):
- Tab indentation (width 2)
- Double quotes
- Organize imports enabled
- Run: `docker compose exec frontend npm run check` / `npm run fmt`
