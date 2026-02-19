import { ChatSession } from "@/lib/chat-types";

type ChatSidebarProps = {
  chats: ChatSession[];
  activeChatId: string | null;
  onSelectChat: (chatId: string) => void;
  onCreateChat: () => void;
};

function formatTimeLabel(value: string) {
  const date = new Date(value);
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ChatSidebar({
  chats,
  activeChatId,
  onSelectChat,
  onCreateChat,
}: ChatSidebarProps) {
  return (
    <aside className="chat-sidebar">
      <div className="sidebar-header">
        <h1>Chats</h1>
        <button className="primary" onClick={onCreateChat}>
          New Chat
        </button>
      </div>
      <div className="chat-list">
        {chats.map((chat) => {
          const lastMessage = chat.messages[chat.messages.length - 1];
          return (
            <button
              key={chat.id}
              className={`chat-list-item ${
                activeChatId === chat.id ? "active" : ""
              }`}
              onClick={() => onSelectChat(chat.id)}
            >
              <div className="chat-list-head">
                <strong>{chat.title}</strong>
                <span>{formatTimeLabel(chat.updatedAt)}</span>
              </div>
              <p>{lastMessage ? lastMessage.text : "No messages yet"}</p>
              <small>
                {chat.datasource
                  ? `Source: ${chat.datasource.name}`
                  : "No data source attached"}
              </small>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
