import { describe, expect, it } from "vitest";
import { parseSseFrame } from "../src/lib/api";

describe("parseSseFrame", () => {
  it("parses token frames", () => {
    expect(parseSseFrame('data: {"token":"hi "}')).toEqual({ token: "hi " });
  });
  it("detects done sentinel", () => {
    expect(parseSseFrame("data: [DONE]")).toEqual({ done: true });
  });
  it("tolerates malformed frames", () => {
    expect(parseSseFrame("data: {oops")).toEqual({});
  });
});

describe("parseSseFrame meta + done", () => {
  it("parses meta frames", () => {
    const f = parseSseFrame('data: {"meta":{"provider":"mini","tool_calls":[]}}');
    expect(f.meta?.provider).toBe("mini");
  });
  it("still detects done", () => {
    expect(parseSseFrame("data: [DONE]").done).toBe(true);
  });
  it("ignores malformed frames", () => {
    expect(parseSseFrame("data: not-json")).toEqual({});
  });
});

describe("parseSseFrame tool events", () => {
  it("parses tool_event frames", () => {
    const f = parseSseFrame('data: {"tool_event":{"tool":"calculator","args":{},"result":"4"}}');
    expect(f.toolEvent?.tool).toBe("calculator");
    expect(f.toolEvent?.result).toBe("4");
  });
});

describe("conversations client (session bar / new-session contract)", () => {
  it("create POSTs to /api/conversations and returns the new row", async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    const orig = globalThis.fetch;
    globalThis.fetch = ((url: string, init?: RequestInit) => {
      calls.push({ url, init });
      return Promise.resolve(new Response(JSON.stringify(
        { id: "c-42", title: "untitled", updated_at: 0 })));
    }) as typeof fetch;
    try {
      const { conversations } = await import("../src/lib/api");
      const c = await conversations.create();
      expect(calls[0].url).toBe("/api/conversations");
      expect(calls[0].init?.method).toBe("POST");
      expect(c.id).toBe("c-42");
    } finally {
      globalThis.fetch = orig;
    }
  });

  it("messages encodes the conversation id into the query", async () => {
    const urls: string[] = [];
    const orig = globalThis.fetch;
    globalThis.fetch = ((url: string) => {
      urls.push(url);
      return Promise.resolve(new Response("[]"));
    }) as typeof fetch;
    try {
      const { conversations } = await import("../src/lib/api");
      await conversations.messages("a b/c"); // hostile id: must be encoded
      expect(urls[0]).toBe("/api/messages?conversation_id=a%20b%2Fc");
    } finally {
      globalThis.fetch = orig;
    }
  });
});
