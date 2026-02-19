import { ChatSession, PersistedChatSession } from "@/lib/chat-types";

const STORAGE_KEY = "text2sql_chat_sessions_v1";
const ACTIVE_CHAT_KEY = "text2sql_active_chat_v1";

export function loadChatState(): {
  chats: ChatSession[];
  activeChatId: string | null;
} {
  if (typeof window === "undefined") {
    return { chats: [], activeChatId: null };
  }

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const activeChatId = localStorage.getItem(ACTIVE_CHAT_KEY);
    if (!raw) {
      return { chats: [], activeChatId };
    }

    const parsed = JSON.parse(raw) as PersistedChatSession[];
    const chats: ChatSession[] = parsed.map((chat) => ({
      ...chat,
      isLoading: false,
      error: null,
    }));
    return { chats, activeChatId };
  } catch {
    return { chats: [], activeChatId: null };
  }
}

export function saveChatState(chats: ChatSession[], activeChatId: string | null) {
  if (typeof window === "undefined") return;

  const persistable: PersistedChatSession[] = chats.map(
    ({ isLoading: _isLoading, error: _error, ...chat }) => chat
  );

  localStorage.setItem(STORAGE_KEY, JSON.stringify(persistable));
  if (activeChatId) {
    localStorage.setItem(ACTIVE_CHAT_KEY, activeChatId);
  } else {
    localStorage.removeItem(ACTIVE_CHAT_KEY);
  }
}
