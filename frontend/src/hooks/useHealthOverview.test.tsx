import { describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { useHealthCategory, useHealthView } from "./useHealthOverview";
import * as api from "../lib/api";

const view = {
  state: "ready" as const,
  snapshot_version: "1.unified-1.abc",
  overview: { available: true, categories: [], disclaimer: "", overall_question: "Help me understand" },
  categories: { liver_health: { id: "liver_health", name: "Liver", findings: [{ id: "hdl", name: "HDL" }] } },
  findings: {},
  related_keys: {},
  suggested_questions: {},
};

function wrap(client: QueryClient) {
  return ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("health view cache", () => {
  it("opens a warm category without another HTTP call", async () => {
    const getHealthView = vi.spyOn(api, "getHealthView").mockResolvedValue(view as never);
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({ user_id: "one", display_name: "A" } as never);
    const category = vi.spyOn(api, "getHealthCategory");
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useHealthCategory("liver_health"), { wrapper: wrap(client) });
    await waitFor(() => expect(result.current.data?.id).toBe("liver_health"));
    expect(getHealthView).toHaveBeenCalledTimes(1);
    expect(category).not.toHaveBeenCalled();
  });

  it("drops the previous member view when the subject changes", async () => {
    vi.spyOn(api, "getHealthView").mockResolvedValue(view as never);
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({ user_id: "one" } as never);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderHook(() => useHealthView(), { wrapper: wrap(client) });
    await waitFor(() => expect(client.getQueryData(["health-view", "one"])).toBeTruthy());
    client.setQueryData(["me"], { user_id: "two" });
    await waitFor(() => expect(client.getQueryData(["health-view", "one"])).toBeUndefined());
  });
});
