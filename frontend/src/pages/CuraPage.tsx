import { useCallback, useLayoutEffect, useRef, useState } from "react";
import { useStickToBottom } from "../hooks/useStickToBottom";
import { useCuraChat } from "../hooks/useCuraChat";
import { useMe } from "../hooks/useMe";
import { AppShell } from "../components/AppShell";
import { Composer } from "../components/Composer";
import { CuraHeader } from "../components/CuraHeader";
import { DocumentPanel } from "../components/DocumentPanel";
import { MessageList } from "../components/MessageList";
import { ConversationSidebar } from "../components/ConversationSidebar";
import { ExploreJourney } from "../components/explore/ExploreJourney";
import { WelcomeExperience } from "../components/WelcomeExperience";
import type { ContextRef } from "../types/chat";
import { useOverview } from "../hooks/useOverview";
import { useHealthView } from "../hooks/useHealthOverview";
import { MarkerPanel } from "../components/marker/MarkerPanel";
import { MarkerPanelProvider } from "../components/marker/MarkerPanelContext";
import { useDocumentUpload } from "../hooks/useDocumentUpload";
import { PageDropZone } from "../components/documents/PageDropZone";
import { ReviewValues } from "../components/documents/ReviewValues";
import { sendFeedback } from "../lib/api";

export function CuraPage() {
  const {
    messages,
    loading,
    processingSteps,
    error,
    failed,
    retryFailed,
    send,
    editAndResend,
    conversationId,
    conversationEpoch,
    suggestions,
    newConversation,
    resumeConversation,
  } = useCuraChat();
  const { me, loading: meLoading } = useMe();
  const health = useHealthView();
  const [docTick, setDocTick] = useState(0);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
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

  const [returning] = useState(() => {
    try {
      const seen = window.localStorage.getItem("cura_seen") === "1";
      window.localStorage.setItem("cura_seen", "1");
      return seen;
    } catch {
      return false;
    }
  });
  const [showExplore, setShowExplore] = useState(false);
  const [place, setPlace] = useState<"home" | "overview" | "category" | "marker" | "risk">("home");
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [findingId, setFindingId] = useState<string | null>(null);
  const spots = useRef<Record<string, number>>({});
  const spotKey = `${place}|${categoryId ?? ""}|${findingId ?? ""}`;
  function rememberScroll() {
    if (scrollRef.current) spots.current[spotKey] = scrollRef.current.scrollTop;
  }
  function askFromOverview(text: string, contextRef: ContextRef) {
    rememberScroll();
    setShowExplore(false);
    void sendWithContext(text, [], contextRef);
  }
  useLayoutEffect(() => {
    if (showExplore && scrollRef.current) scrollRef.current.scrollTop = spots.current[spotKey] || 0;
  }, [showExplore, spotKey]);

  // One step back each time: out of an opened card, then out of the overview, then out of a chat.
  const started = messages.length > 0;
  const goBack = !showExplore && started
    ? () => setShowExplore(true)
    : showExplore && place !== "overview"
      ? () => {
          rememberScroll();
          setPlace(place === "category" ? "overview" : "category");
        }
      : showExplore
        ? () => setShowExplore(false)
        : undefined;

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
    setShowExplore(false);
    setPlace("overview");
    setCategoryId(null);
    setFindingId(null);
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
      <CuraHeader onOpenSidebar={() => setDrawerOpen(true)} onBack={goBack} />
      <div className="main-scroll" ref={scrollRef}>
        {showExplore && (
          <ExploreJourney
            view={health.data}
            loading={health.isLoading || meLoading}
            error={health.isError}
            name={me?.display_name || me?.first_name || null}
            place={place === "home" ? "overview" : place}
            categoryId={categoryId}
            findingId={findingId}
            onPlace={(next, category, finding) => {
              if (next === "home") {
                setShowExplore(false);
                setPlace("overview");
                return;
              }
              setPlace(next);
              if (category !== undefined) setCategoryId(category);
              if (finding !== undefined) setFindingId(finding ?? null);
            }}
            onAsk={askFromOverview}
          />
        )}
        {!showExplore && !started && (
          <WelcomeExperience
            returning={returning}
            me={me}
            meLoading={meLoading}
            suggestions={suggestions}
            onSend={(text, ids, ref) => {
              setShowExplore(false);
              void sendWithContext(text, ids, ref);
            }}
            onOpenOverview={() => {
              setPlace("overview");
              setCategoryId(null);
              setFindingId(null);
              setShowExplore(true);
            }}
            inputRef={inputRef}
          />
        )}
        <DocumentPanel
          refreshKey={docTick}
          selected={selectedDocumentIds}
          onSelectedChange={setSelectedDocumentIds}
          onReview={setReviewId}
        />
        {!showExplore && <MessageList
          messages={messages}
          onFollowUp={(text) => sendWithContext(text)}
          onAskContext={(text, ref) => sendWithContext(text, [], ref)}
          onFeedback={(rating, comment) => {
            if (conversationId) void sendFeedback(conversationId, rating, comment).catch(() => undefined);
          }}
          onEditQuestion={(index, text) => {
            if (!loading) void editAndResend(index, text);
          }}
          editingDisabled={loading}
          processingEvents={loading ? processingSteps : []}
        />}
        {error && (
          <div className="error-banner" role="alert">
            <p>{error}</p>
            {failed && (
              <button type="button" className="text-button" onClick={retryFailed} disabled={loading}>
                Try again
              </button>
            )}
          </div>
        )}
      </div>
      <div className="composer-dock">
        <Composer
          disabled={loading}
          onSend={sendWithContext}
          restoreText={failed?.text}
          inputRef={inputRef}
          conversationId={conversationId}
          onUploaded={refreshDocuments}
          uploader={uploader}
          onReview={setReviewId}
          voiceEnabled={me?.capabilities?.voice_input !== false}
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
