import { describe, expect, it } from "vitest";
import { recentSafeTopic, selectGreeting, type GreetingInput } from "./selectGreeting";
import { readVisit } from "./visitState";

const now = "2026-11-26T00:00:00.000Z";

function input(over: Partial<GreetingInput> = {}): GreetingInput {
  return {
    firstName: "Neha",
    hasConversations: false,
    reportsKnown: true,
    hasReports: true,
    hasUnexploredReport: false,
    previousVisitAt: null,
    now,
    recentTopic: null,
    ...over,
  };
}

describe("selectGreeting", () => {
  it("uses the first-time greeting when reports exist", () => {
    expect(selectGreeting(input()).id).toBe("first_with_reports");
    expect(selectGreeting(input()).heading).toBe("Hi Neha 👋");
  });

  it("uses the no-report greeting for a first visit with confirmed empty data", () => {
    expect(selectGreeting(input({ hasReports: false })).id).toBe("no_reports");
  });

  it("does not treat unknown health data as an empty record", () => {
    expect(selectGreeting(input({ reportsKnown: false, hasReports: false })).id).toBe("returning");
  });

  it("does not treat a failed history request as a first visit", () => {
    expect(selectGreeting(input({ hasConversations: null })).id).toBe("returning");
  });

  it("prefers a new report over a long absence and a recent topic", () => {
    const choice = selectGreeting(input({
      hasConversations: true,
      hasUnexploredReport: true,
      previousVisitAt: "2026-01-01T00:00:00.000Z",
      recentTopic: "your vitamin D levels",
    }));
    expect(choice.id).toBe("new_report");
  });

  it("uses the long-absence greeting after 30 days when no new report is waiting", () => {
    expect(selectGreeting(input({
      hasConversations: true,
      previousVisitAt: "2026-10-01T00:00:00.000Z",
      recentTopic: "your vitamin D levels",
    })).id).toBe("long_absence");
  });

  it("continues a safe recent topic", () => {
    const choice = selectGreeting(input({
      hasConversations: true,
      previousVisitAt: "2026-11-20T00:00:00.000Z",
      recentTopic: "your vitamin D levels",
    }));
    expect(choice.id).toBe("continue_conversation");
    expect(choice.supporting).toBe("Last time, we talked about your vitamin D levels. We can explore it a little further or talk about something new today.");
  });

  it("uses the returning greeting when the recent topic is sensitive", () => {
    expect(recentSafeTopic([{ title: "My chest pain", updated_at: "2026-11-25T00:00:00.000Z" }], now)).toBeNull();
    expect(selectGreeting(input({
      hasConversations: true,
      previousVisitAt: "2026-11-20T00:00:00.000Z",
      recentTopic: null,
    })).id).toBe("returning");
  });

  it("drops the name when it is missing", () => {
    expect(selectGreeting(input({ firstName: null })).heading).toBe("Hi there 👋");
    expect(selectGreeting(input({ firstName: null, hasConversations: true, previousVisitAt: "2026-11-20T00:00:00.000Z" })).heading).toBe("Welcome back 👋");
  });

  it("keeps the same greeting after a refresh in the same session", () => {
    const local = new Map<string, string>();
    const session = new Map<string, string>();
    const storage = {
      getItem: (k: string) => local.get(k) ?? null,
      setItem: (k: string, v: string) => { local.set(k, v); },
    } as Storage;
    const sessions = {
      getItem: (k: string) => session.get(k) ?? null,
      setItem: (k: string, v: string) => { session.set(k, v); },
    } as Storage;
    const first = readVisit("user-a", now, storage, sessions);
    const refresh = readVisit("user-a", now, storage, sessions);
    expect(first.previousVisitAt).toBeNull();
    expect(refresh.previousVisitAt).toBeNull();
    const other = readVisit("user-b", now, storage, sessions);
    expect(other.previousVisitAt).toBeNull();
    expect(local.has("cura_home:user-a")).toBe(true);
    expect(local.has("cura_home:user-b")).toBe(true);
  });
});
