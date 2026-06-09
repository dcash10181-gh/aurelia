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
