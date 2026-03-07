import { DataSourceInfo, QueryResponse } from "@/lib/api";

export type ChatRole = "user" | "assistant" | "system";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  text: string;
  createdAt: string;
  result?: QueryResponse;
};

export type ChatSession = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  datasource: DataSourceInfo | null;
  knowledgeSpaceId?: string | null;
  knowledgeSpaceName?: string | null;
  ingestionStatus?: string | null;
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
};

export type PersistedChatSession = Omit<ChatSession, "isLoading" | "error">;
