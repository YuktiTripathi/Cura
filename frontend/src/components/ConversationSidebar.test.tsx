import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithQuery as render } from "../test/render";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConversationSidebar } from "../components/ConversationSidebar";
import { CuraPage } from "../pages/CuraPage";
import type { ConversationSummary } from "../lib/api";

const conversations: ConversationSummary[] = [];

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    getCurrentUser: vi.fn(async () => ({
      user_id: "demo-user-001",
      first_name: "Yukti",
      last_name: "Tripathi",
      display_name: "Yukti",
      greeting: "Hi Yukti 👋",
      profile_available: true,
      capabilities: {
        has_blood_report: true,
        has_bio_ai_report: true,
        has_questionnaire: false,
        has_nutrition: true,
        has_health_scenario: true,
      },
      starters: {
        personal: [{ text: "What is my latest HbA1c?", knowledge_scope: "personal", category: "blood" }],
        general: [{ text: "What does HbA1c measure?", knowledge_scope: "general", category: "general_education" }],
        personal_unavailable: false,
      },
    })),
    listConversations: vi.fn(async () => [...conversations]),
    getConversation: vi.fn(async (id: string) => ({
      id,
      title: conversations.find((c) => c.id === id)?.title || "Cura conversation",
      messages: [
        { id: "m1", role: "user" as const, content: "What is my HbA1c?", created_at: "" },
        { id: "m2", role: "assistant" as const, content: "Your HbA1c is 5.5%.", created_at: "" },
      ],
    })),
    deleteConversation: vi.fn(async (id: string) => {
      const idx = conversations.findIndex((c) => c.id === id);
      if (idx >= 0) conversations.splice(idx, 1);
    }),
    streamChat: vi.fn(),
    sendFeedback: vi.fn(),
    listDocuments: vi.fn(async () => []),
    getOverview: vi.fn(async () => ({ available: false, markers: [], insights: [], scores: [], reports: [] })),
  };
});

describe("ConversationSidebar", () => {
  afterEach(() => {
    cleanup();
    conversations.splice(0, conversations.length);
  });

  it("stays visible with an empty state", async () => {
    render(
      <ConversationSidebar
        refreshKey={1}
        activeId={null}
        onOpen={() => undefined}
        onNew={() => undefined}
        onDeleted={() => undefined}
        mobileOpen={false}
        onCloseMobile={() => undefined}
      />
    );
    await waitFor(() => {
      expect(screen.getByText("Recent conversations")).toBeTruthy();
    });
    expect(await screen.findByText("No conversations yet.")).toBeTruthy();
    expect(screen.getByText("Start a conversation with Cura to see it here.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "+ New conversation" })).toBeTruthy();
  });

  it("marks the active conversation and supports switch/delete", async () => {
    conversations.push(
      { id: "c1", title: "Understanding my HbA1c", updated_at: "" },
      { id: "c2", title: "Nutrition guidance", updated_at: "" }
    );
    const onOpen = vi.fn();
    const onDeleted = vi.fn();
    render(
      <ConversationSidebar
        refreshKey={2}
        activeId="c1"
        onOpen={onOpen}
        onNew={() => undefined}
        onDeleted={onDeleted}
        mobileOpen={false}
        onCloseMobile={() => undefined}
      />
    );
    await waitFor(() => {
      expect(screen.getByText(/Understanding my HbA1c/)).toBeTruthy();
    });
    expect(document.querySelector(".conversation-row.active")?.textContent).toContain("Understanding my HbA1c");
    fireEvent.click(screen.getByText(/Nutrition guidance/));
    await waitFor(() => expect(onOpen).toHaveBeenCalled());
    fireEvent.click(screen.getByLabelText("Delete Nutrition guidance"));
    await waitFor(() => expect(onDeleted).toHaveBeenCalledWith("c2"));
    expect(screen.queryByText(/Nutrition guidance/)).toBeNull();
  });
});

describe("CuraPage shell", () => {
  beforeEach(() => {
    conversations.splice(0, conversations.length);
    window.sessionStorage.clear();
  });
  afterEach(() => cleanup());

  it("puts recent conversations in the left sidebar, not between greeting and cards", async () => {
    render(<CuraPage />);
    await waitFor(() => {
      expect(screen.getByText("Hi Yukti 👋")).toBeTruthy();
    });
    expect(screen.getByText("How can I help you understand your health better?")).toBeTruthy();
    expect(screen.getByText("My Blood Report")).toBeTruthy();
    expect(screen.getByText("My Bio-AI Report")).toBeTruthy();
    expect(screen.queryByText("My Health Scenario")).toBeNull();
    expect(screen.getByRole("button", { name: /Nutrition/ })).toBeTruthy();
    const welcome = screen.getByText("How can I help you understand your health better?").closest("section");
    expect(welcome?.textContent).toContain("Nutrition");
    expect(screen.getByText("Ask Cura")).toBeTruthy();
    expect(screen.getByText("Based on your health")).toBeTruthy();
    expect(screen.getByText("Learn about health")).toBeTruthy();
    const sidebar = document.querySelector("aside.sidebar");
    expect(sidebar).toBeTruthy();
    expect(sidebar?.textContent).toContain("Recent conversations");
    expect(document.querySelector(".page")).toBeNull();
  });
});
