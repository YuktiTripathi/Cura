import { afterEach, describe, expect, it, vi } from "vitest";
import { streamChat } from "./api";

function sse(frames: Array<[string, unknown]>): Response {
  const body = frames.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join("");
  const bytes = new TextEncoder().encode(body);
  const stream = new ReadableStream({
    start(controller) {
      // Split mid-frame to exercise buffering across reads.
      controller.enqueue(bytes.slice(0, 40));
      controller.enqueue(bytes.slice(40));
      controller.close();
    },
  });
  return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

describe("streamChat", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("delivers progress and preview events before resolving with the final answer", async () => {
    const finding = { label: "LDL cholesterol", value: "138.0", unit: "mg/dL", numeric_value: 138, reference_high: 100 };
    const final = { conversation_id: "c1", answer: "Your LDL is 138 mg/dL.", evidence: [], follow_ups: [], meta: {} };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        sse([
          ["status", { state: "started" }],
          ["progress", { stage: "FETCHING_BLOOD_DATA", message_key: "blood.fetch" }],
          ["preview", { findings: [finding] }],
          ["complete", final],
          ["answer", final],
        ])
      )
    );
    const order: string[] = [];
    const previews: unknown[] = [];
    const res = await streamChat(
      "What is my LDL?",
      null,
      [],
      undefined,
      () => undefined,
      (event) => order.push(`progress:${event.stage}`),
      (preview) => {
        order.push("preview");
        previews.push(preview);
      }
    );
    expect(order).toEqual(["progress:FETCHING_BLOOD_DATA", "preview"]);
    expect(previews).toEqual([{ findings: [finding] }]);
    expect(res.answer).toBe("Your LDL is 138 mg/dL.");
  });

  it("delivers validated experience blocks before the final response", async () => {
    const block = { sequence: 0, kind: "direct_answer", text: "Your LDL is 138 mg/dL.", findings: [] };
    const final = {
      conversation_id: "c2",
      answer: "Your LDL is 138 mg/dL.",
      evidence: [],
      follow_ups: [],
      meta: {},
      experience: { stream_policy: "SEMANTIC_BLOCKS", key_facts: [], uncertainties: [], next_steps: [], blocks: [block] },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        sse([
          ["status", { state: "started" }],
          ["experience_block", block],
          ["complete", final],
        ])
      )
    );
    const blocks: unknown[] = [];
    const res = await streamChat(
      "Why is my LDL high?",
      null,
      [],
      undefined,
      () => undefined,
      undefined,
      undefined,
      (item) => blocks.push(item)
    );
    expect(blocks).toEqual([block]);
    expect(res.experience?.stream_policy).toBe("SEMANTIC_BLOCKS");
  });

});
