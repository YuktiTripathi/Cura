import { afterEach, describe, expect, it, vi } from "vitest";
import { sendChat, streamChat } from "./api";

function json(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });
}

function sse(frames: string[]): Response {
  return new Response(frames.join(""), { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

const answer = { conversation_id: "c1", answer: "ok", meta: {} };

afterEach(() => vi.unstubAllGlobals());

describe("chat client retries", () => {
  it("retries network errors and 503 with the same Idempotency-Key", async () => {
    const keys: string[] = [];
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(async (_url: string, init: RequestInit) => {
        keys.push((init.headers as Record<string, string>)["Idempotency-Key"]);
        throw new TypeError("network down");
      })
      .mockImplementationOnce(async (_url: string, init: RequestInit) => {
        keys.push((init.headers as Record<string, string>)["Idempotency-Key"]);
        return json(503, { error: { message: "busy" } }, { "Retry-After": "0" });
      })
      .mockImplementationOnce(async (_url: string, init: RequestInit) => {
        keys.push((init.headers as Record<string, string>)["Idempotency-Key"]);
        return json(200, answer);
      });
    vi.stubGlobal("fetch", fetchMock);
    const res = await sendChat("hi", null);
    expect(res.answer).toBe("ok");
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(new Set(keys).size).toBe(1);
    expect(keys[0]).toBeTruthy();
  });

  it("does not retry a 400", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(400, { error: { message: "bad request" } }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(sendChat("hi", null)).rejects.toThrow("bad request");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("reconnects a dropped stream once and gets the finished answer", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(sse(['event: status\ndata: {"state":"started"}\n\n']))
      .mockResolvedValueOnce(sse([`event: complete\ndata: ${JSON.stringify(answer)}\n\n`]));
    vi.stubGlobal("fetch", fetchMock);
    const res = await streamChat("hi", null, [], undefined, () => {});
    expect(res.answer).toBe("ok");
    const [first, second] = fetchMock.mock.calls.map((call) => (call[1].headers as Record<string, string>)["Idempotency-Key"]);
    expect(first).toBe(second);
  });

  it("does not reconnect after a server error event", async () => {
    const fetchMock = vi.fn().mockResolvedValue(sse(['event: error\ndata: {"message":"nope"}\n\n']));
    vi.stubGlobal("fetch", fetchMock);
    await expect(streamChat("hi", null, [], undefined, () => {})).rejects.toThrow("nope");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
