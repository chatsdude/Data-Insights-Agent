"use client";

import { useEffect, useMemo, useState } from "react";

import { ChatSidebar } from "@/components/ChatSidebar";
import { ChatWindow } from "@/components/ChatWindow";
import {
  DataSourceInfo,
  KnowledgeSpaceInfo,
  QueryResponse,
  createKnowledgeSpace,
  getIngestionJob,
  listKnowledgeSpaces,
  registerCSV,
  registerSQLite,
  uploadKnowledgeDocument,
  runQueryStream,
} from "@/lib/api";
import { ChatMessage, ChatSession } from "@/lib/chat-types";

function makeId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function getMessagePreview(text: string) {
  return text.length > 44 ? `${text.slice(0, 44)}...` : text;
}

function createChat(): ChatSession {
  const now = new Date().toISOString();
  return {
    id: makeId(),
    title: "New chat",
    createdAt: now,
    updatedAt: now,
    datasource: null,
    knowledgeSpaceId: null,
    knowledgeSpaceName: null,
    ingestionStatus: null,
    messages: [],
    isLoading: false,
    error: null,
  };
}

function updateChatById(
  chats: ChatSession[],
  chatId: string,
  update: (chat: ChatSession) => ChatSession
) {
  return chats.map((chat) => (chat.id === chatId ? update(chat) : chat));
}

export default function HomePage() {
  const [initialChat] = useState<ChatSession>(() => createChat());
  const [chats, setChats] = useState<ChatSession[]>(() => [initialChat]);
  const [activeChatId, setActiveChatId] = useState<string | null>(
    () => initialChat.id
  );
  const [draft, setDraft] = useState("");
  const [visualizeResults, setVisualizeResults] = useState(false);
  const [knowledgeSpaces, setKnowledgeSpaces] = useState<KnowledgeSpaceInfo[]>([]);

  const activeChat = useMemo(
    () => chats.find((chat) => chat.id === activeChatId) ?? null,
    [chats, activeChatId]
  );

  useEffect(() => {
    let isActive = true;
    listKnowledgeSpaces()
      .then((spaces) => {
        if (!isActive) return;
        setKnowledgeSpaces(spaces);
      })
      .catch(() => undefined);
    return () => {
      isActive = false;
    };
  }, []);

  useEffect(() => {
    if (!activeChatId || knowledgeSpaces.length === 0) return;
    const defaultSpace = knowledgeSpaces[0];
    setChats((prev) =>
      updateChatById(prev, activeChatId, (chat) => {
        if (chat.knowledgeSpaceId) return chat;
        return {
          ...chat,
          knowledgeSpaceId: defaultSpace.id,
          knowledgeSpaceName: defaultSpace.name,
          updatedAt: new Date().toISOString(),
        };
      })
    );
  }, [activeChatId, knowledgeSpaces]);

  const addSystemMessage = (chatId: string, text: string) => {
    const now = new Date().toISOString();
    const systemMessage: ChatMessage = {
      id: makeId(),
      role: "system",
      text,
      createdAt: now,
    };

    setChats((prev) =>
      updateChatById(prev, chatId, (chat) => ({
        ...chat,
        updatedAt: now,
        messages: [...chat.messages, systemMessage],
      }))
    );
  };

  const handleCreateChat = () => {
    const next = createChat();
    setChats((prev) => [next, ...prev]);
    setActiveChatId(next.id);
    setDraft("");
    setVisualizeResults(false);
  };

  const handleSelectChat = (chatId: string) => {
    setActiveChatId(chatId);
    setDraft("");
    setVisualizeResults(false);
  };

  const setActiveChatLoading = (loading: boolean) => {
    if (!activeChatId) return;
    setChats((prev) =>
      updateChatById(prev, activeChatId, (chat) => ({
        ...chat,
        isLoading: loading,
      }))
    );
  };

  const attachDatasource = async (
    file: File,
    registerFn: (file: File) => Promise<DataSourceInfo>
  ) => {
    if (!activeChatId) return;

    try {
      setActiveChatLoading(true);
      setChats((prev) =>
        updateChatById(prev, activeChatId, (chat) => ({
          ...chat,
          error: null,
        }))
      );

      const datasource = await registerFn(file);
      const now = new Date().toISOString();
      setChats((prev) =>
        updateChatById(prev, activeChatId, (chat) => ({
          ...chat,
          datasource,
          updatedAt: now,
        }))
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Upload failed.";
      setChats((prev) =>
        updateChatById(prev, activeChatId, (chat) => ({
          ...chat,
          error: message,
        }))
      );
    } finally {
      setActiveChatLoading(false);
    }
  };

  const handleSelectKnowledgeSpace = (spaceId: string) => {
    if (!activeChatId) return;
    const picked = knowledgeSpaces.find((space) => space.id === spaceId) ?? null;
    const now = new Date().toISOString();
    setChats((prev) =>
      updateChatById(prev, activeChatId, (chat) => ({
        ...chat,
        knowledgeSpaceId: spaceId || null,
        knowledgeSpaceName: picked?.name ?? null,
        updatedAt: now,
      }))
    );
  };

  const handleCreateKnowledgeSpace = async (name: string) => {
    if (!activeChatId || !name) return;
    try {
      const created = await createKnowledgeSpace(name);
      setKnowledgeSpaces((prev) => [created, ...prev]);
      const now = new Date().toISOString();
      setChats((prev) =>
        updateChatById(prev, activeChatId, (chat) => ({
          ...chat,
          knowledgeSpaceId: created.id,
          knowledgeSpaceName: created.name,
          updatedAt: now,
        }))
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not create space.";
      setChats((prev) =>
        updateChatById(prev, activeChatId, (chat) => ({
          ...chat,
          error: message,
        }))
      );
    }
  };

  const pollIngestionStatus = async (chatId: string, jobId: string) => {
    for (let i = 0; i < 60; i += 1) {
      const job = await getIngestionJob(jobId);
      const statusText = `${job.status} (${job.stage} ${job.progress}%)`;
      setChats((prev) =>
        updateChatById(prev, chatId, (chat) => ({
          ...chat,
          ingestionStatus: statusText,
        }))
      );
      if (job.status === "completed") return;
      if (job.status === "failed") {
        throw new Error(job.error || "Ingestion failed.");
      }
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
    throw new Error("Ingestion is still running. Check again in a minute.");
  };

  const handleUploadKnowledgeDoc = async (file: File) => {
    if (!activeChatId || !activeChat?.knowledgeSpaceId) return;
    const chatId = activeChatId;
    try {
      setChats((prev) =>
        updateChatById(prev, chatId, (chat) => ({
          ...chat,
          error: null,
          ingestionStatus: "queued (uploading...)",
        }))
      );

      const result = await uploadKnowledgeDocument(activeChat.knowledgeSpaceId, file);
      setChats((prev) =>
        updateChatById(prev, chatId, (chat) => ({
          ...chat,
          ingestionStatus: `queued (${result.job.stage} ${result.job.progress}%)`,
        }))
      );
      await pollIngestionStatus(chatId, result.job.id);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Knowledge upload failed.";
      setChats((prev) =>
        updateChatById(prev, chatId, (chat) => ({
          ...chat,
          error: message,
          ingestionStatus: "failed",
        }))
      );
    }
  };

  const handleSend = async () => {
    if (!activeChatId || !activeChat) return;

    const question = draft.trim();
    if (!question) return;

    if (!activeChat.datasource) {
      setChats((prev) =>
        updateChatById(prev, activeChatId, (chat) => ({
          ...chat,
          error: "Attach a data source before sending a question.",
        }))
      );
      return;
    }

    const includeVisualization = visualizeResults;
    setDraft("");
    setVisualizeResults(false);

    const now = new Date().toISOString();
    const userMessage: ChatMessage = {
      id: makeId(),
      role: "user",
      text: question,
      createdAt: now,
    };

    setChats((prev) =>
      updateChatById(prev, activeChatId, (chat) => ({
        ...chat,
        isLoading: true,
        error: null,
        title: chat.title === "New chat" ? getMessagePreview(question) : chat.title,
        updatedAt: now,
        messages: [...chat.messages, userMessage],
      }))
    );

    try {
      const responseTime = new Date().toISOString();
      const assistantMessageId = makeId();
      const initialResult: QueryResponse = {
        status: "progress",
        step: "schema",
        message: "Preparing pipeline",
        sql_query: "",
        columns: [],
        rows: [],
        chart_suggestion: {
          chart_type: "table",
          x_field: null,
          y_field: null,
          series_field: null,
          rationale: "Preparing results.",
        },
        summary_text: "",
        error: null,
      };
      const assistantMessage: ChatMessage = {
        id: assistantMessageId,
        role: "assistant",
        text: "Running query...",
        createdAt: responseTime,
        result: initialResult,
      };

      setChats((prev) =>
        updateChatById(prev, activeChatId, (chat) => ({
          ...chat,
          updatedAt: responseTime,
          messages: [...chat.messages, assistantMessage],
        }))
      );

      let latestResult = initialResult;
      for await (const chunk of runQueryStream(
        activeChat.datasource.id,
        question,
        includeVisualization,
        activeChat.knowledgeSpaceId
      )) {
        latestResult = { ...latestResult, ...chunk };
        const updateTime = new Date().toISOString();
        setChats((prev) =>
          updateChatById(prev, activeChatId, (chat) => ({
            ...chat,
            updatedAt: updateTime,
            messages: chat.messages.map((message) =>
              message.id === assistantMessageId
                ? {
                    ...message,
                    text:
                      latestResult.message ||
                      latestResult.summary_text ||
                      (latestResult.status === "partial"
                        ? "Running query..."
                        : "Query completed."),
                    result: latestResult,
                  }
                : message
            ),
          }))
        );
      }

      const finalTime = new Date().toISOString();
      setChats((prev) =>
        updateChatById(prev, activeChatId, (chat) => ({
          ...chat,
          isLoading: false,
          updatedAt: finalTime,
        }))
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Query failed.";
      const errorTime = new Date().toISOString();

      setChats((prev) =>
        updateChatById(prev, activeChatId, (chat) => ({
          ...chat,
          isLoading: false,
          error: message,
          updatedAt: errorTime,
        }))
      );

      if (message.toLowerCase().includes("datasource not found")) {
        setChats((prev) =>
          updateChatById(prev, activeChatId, (chat) => ({
            ...chat,
            datasource: null,
          }))
        );
        addSystemMessage(
          activeChatId,
          "The linked data source is no longer available. Reattach a source to continue."
        );
      }
    }
  };

  return (
    <main className="chat-app">
      <ChatSidebar
        chats={chats}
        activeChatId={activeChatId}
        onSelectChat={handleSelectChat}
        onCreateChat={handleCreateChat}
      />
      {activeChat ? (
        <ChatWindow
          chat={activeChat}
          knowledgeSpaces={knowledgeSpaces}
          draft={draft}
          visualizeResults={visualizeResults}
          onDraftChange={setDraft}
          onVisualizeResultsChange={setVisualizeResults}
          onSend={handleSend}
          onUploadCsv={(file) => attachDatasource(file, registerCSV)}
          onUploadSqlite={(file) => attachDatasource(file, registerSQLite)}
          onSelectKnowledgeSpace={handleSelectKnowledgeSpace}
          onCreateKnowledgeSpace={handleCreateKnowledgeSpace}
          onUploadKnowledgeDoc={handleUploadKnowledgeDoc}
        />
      ) : (
        <section className="chat-main empty">
          <p>No chat selected.</p>
        </section>
      )}
    </main>
  );
}
