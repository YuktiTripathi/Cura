import { useRef, useState } from "react";
import { useCuraChat } from "../hooks/useCuraChat";
import { useMe } from "../hooks/useMe";
import { AppShell } from "../components/AppShell";
import { Composer } from "../components/Composer";
import { CuraHeader } from "../components/CuraHeader";
import { DocumentPanel } from "../components/DocumentPanel";
import { ProgressStepper } from "../components/ProgressStepper";
import { MessageList } from "../components/MessageList";
import { ConversationSidebar } from "../components/ConversationSidebar";
import { WelcomeExperience } from "../components/WelcomeExperience";
import type { ContextRef } from "../types/chat";
import { sendFeedback } from "../lib/api";

export function CuraPage() {
  const {
    messages,
    loading,
    processingSteps,
    error,
    send,
    editAndResend,
    conversationId,
    conversationEpoch,
    newConversation,
    resumeConversation,
  } = useCuraChat();
  const { me, loading: meLoading } = useMe();
  const [docTick, setDocTick] = useState(0);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const started = messages.length > 0;
  const inputRef = useRef<HTMLInputElement>(null);

  function sendWithContext(text: string, documentIds: string[] = [], contextRef?: ContextRef) {
    const ids = Array.from(new Set([...selectedDocumentIds, ...documentIds]));
    return send(text, ids, contextRef);
  }

  function startNew() {
    newConversation();
    setSelectedDocumentIds([]);
    setDrawerOpen(false);
  }

  return (
    <AppShell
      drawerOpen={drawerOpen}
      onCloseDrawer={() => setDrawerOpen(false)}
      sidebar={
        <ConversationSidebar
          refreshKey={conversationEpoch}
          activeId={conversationId}
          onOpen={resumeConversation}
          onNew={startNew}
          onDeleted={(id) => {
            if (id === conversationId) startNew();
          }}
          mobileOpen={drawerOpen}
          onCloseMobile={() => setDrawerOpen(false)}
        />
      }
    >
      <CuraHeader onOpenSidebar={() => setDrawerOpen(true)} />
      <div className="main-scroll">
        {!started && (
          <WelcomeExperience me={me} meLoading={meLoading} onSend={sendWithContext} inputRef={inputRef} />
        )}
        <DocumentPanel
          refreshKey={docTick}
          selected={selectedDocumentIds}
          onSelectedChange={setSelectedDocumentIds}
        />
        <MessageList
          messages={messages}
          onFollowUp={(text) => sendWithContext(text)}
          onAskContext={(text, ref) => sendWithContext(text, [], ref)}
          onFeedback={(rating) => {
            if (conversationId) void sendFeedback(conversationId, rating);
          }}
          onEditQuestion={(index, text) => {
            if (!loading) void editAndResend(index, text);
          }}
          editingDisabled={loading}
        />
        {loading && <ProgressStepper events={processingSteps} />}
        {error && <p className="error">{error}</p>}
      </div>
      <div className="composer-dock">
        <Composer
          disabled={loading}
          onSend={sendWithContext}
          inputRef={inputRef}
          conversationId={conversationId}
          onUploaded={() => setDocTick((n) => n + 1)}
        />
        <footer>
          Cura provides educational information, not diagnosis or medication advice.
        </footer>
      </div>
    </AppShell>
  );
}
