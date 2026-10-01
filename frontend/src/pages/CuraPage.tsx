import { useCallback, useRef, useState } from "react";
import { readLanguage, writeLanguage, type LanguageCode } from "../lib/language";
import { useStickToBottom } from "../hooks/useStickToBottom";
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
import { useOverview } from "../hooks/useOverview";
import { MarkerPanel } from "../components/marker/MarkerPanel";
import { MarkerPanelProvider } from "../components/marker/MarkerPanelContext";
import { useDocumentUpload } from "../hooks/useDocumentUpload";
import { PageDropZone } from "../components/documents/PageDropZone";
import { ReviewValues } from "../components/documents/ReviewValues";
import { sendFeedback } from "../lib/api";

export function CuraPage() {
  const [language, setLanguage] = useState<LanguageCode>(readLanguage);
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
  } = useCuraChat(language);
  const { me, loading: meLoading } = useMe(language);
  const [docTick, setDocTick] = useState(0);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const started = messages.length > 0;
  const inputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const userTurns = messages.filter((m) => m.role === "user").length;
  const last = messages[messages.length - 1];
  // Changes whenever visible chat content grows: a message, a progress step, a preview, the answer.
  const contentKey = `${messages.length}:${processingSteps.length}:${last?.preview?.length ?? 0}:${last?.content.length ?? 0}`;
  useStickToBottom(scrollRef, contentKey, userTurns);

  function sendWithContext(text: string, documentIds: string[] = [], contextRef?: ContextRef) {
    const ids = Array.from(new Set([...selectedDocumentIds, ...documentIds]));
    return send(text, ids, contextRef);
  }

  const overview = useOverview();
  const [markerKey, setMarkerKey] = useState<string | null>(null);
  const markers = overview.data?.markers || [];
  const panelMarker = markers.find((m) => m.key === markerKey) || null;
  const markerPanel = {
    has: (key: string | null | undefined) => Boolean(key && markers.some((m) => m.key === key && (m.history?.length ?? 0) > 0)),
    open: (key: string) => setMarkerKey(key),
  };

  function askAboutMarker(text: string, contextRef: ContextRef) {
    // On narrow screens the panel is a sheet over the chat; get it out of the way of the answer.
    if (typeof window.matchMedia === "function" && window.matchMedia("(max-width: 1100px)").matches) setMarkerKey(null);
    void sendWithContext(text, [], contextRef);
  }

  const refreshDocuments = useCallback(() => setDocTick((n) => n + 1), []);
  const uploader = useDocumentUpload(conversationId, refreshDocuments);
  const [reviewId, setReviewId] = useState<string | null>(null);

  function compareDocument(documentId: string) {
    setReviewId(null);
    void sendWithContext("Compare my uploaded report with my SuperShyft results", [documentId]);
  }

  function askAboutDocument(documentId: string) {
    setReviewId(null);
    setSelectedDocumentIds((ids) => Array.from(new Set([...ids, documentId])));
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }

  function startNew() {
    newConversation();
    setSelectedDocumentIds([]);
    setDrawerOpen(false);
  }

  return (
    <MarkerPanelProvider value={markerPanel}>
    <AppShell
      drawerOpen={drawerOpen}
      onCloseDrawer={() => setDrawerOpen(false)}
      panel={
        panelMarker ? (
          <>
            <button type="button" className="marker-panel-backdrop" aria-label="Close marker details" onClick={() => setMarkerKey(null)} />
            <MarkerPanel marker={panelMarker} onClose={() => setMarkerKey(null)} onAsk={askAboutMarker} />
          </>
        ) : null
      }
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
      <CuraHeader
        onOpenSidebar={() => setDrawerOpen(true)}
        language={language}
        onLanguageChange={(code) => {
          writeLanguage(code);
          setLanguage(code);
        }}
      />
      <div className="main-scroll" ref={scrollRef}>
        {!started && (
          <WelcomeExperience me={me} meLoading={meLoading} onSend={sendWithContext} inputRef={inputRef} />
        )}
        <DocumentPanel
          refreshKey={docTick}
          selected={selectedDocumentIds}
          onSelectedChange={setSelectedDocumentIds}
          onReview={setReviewId}
        />
        <MessageList
          messages={messages}
          onFollowUp={(text) => sendWithContext(text)}
          onAskContext={(text, ref) => sendWithContext(text, [], ref)}
          onFeedback={(rating, comment) => {
            if (conversationId) void sendFeedback(conversationId, rating, comment).catch(() => undefined);
          }}
          onRegenerate={(index) => {
            const questionIndex = messages.slice(0, index).map((m) => m.role).lastIndexOf("user");
            if (!loading && questionIndex >= 0) void editAndResend(questionIndex, messages[questionIndex].content);
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
          onUploaded={refreshDocuments}
          uploader={uploader}
          onReview={setReviewId}
          voiceEnabled={me?.capabilities?.voice_input !== false}
          language={language}
        />
        <footer>
          Cura provides educational information, not diagnosis or medication advice.
        </footer>
      </div>
      <PageDropZone onFile={(file) => void uploader.upload(file)} />
      <ReviewValues
        documentId={reviewId}
        onOpenChange={(open) => {
          if (!open) setReviewId(null);
        }}
        onCompare={compareDocument}
        onAsk={askAboutDocument}
      />
    </AppShell>
    </MarkerPanelProvider>
  );
}
