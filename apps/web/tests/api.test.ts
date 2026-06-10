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
