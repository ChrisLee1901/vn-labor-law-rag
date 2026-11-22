import { describe, expect, it } from "vitest";
import { splitCitations } from "./citations";

describe("splitCitations", () => {
  it("splits a single token", () => {
    expect(splitCitations("Mức là 5 triệu [S1].")).toEqual([
      { kind: "text", text: "Mức là 5 triệu " },
      { kind: "cite", id: "S1" },
      { kind: "text", text: "." },
    ]);
  });

  it("handles adjacent tokens", () => {
    expect(splitCitations("a [S1][S2] b")).toEqual([
      { kind: "text", text: "a " },
      { kind: "cite", id: "S1" },
      { kind: "cite", id: "S2" },
      { kind: "text", text: " b" },
    ]);
  });

  it("handles a comma list", () => {
    expect(splitCitations("x [S1, S12]")).toEqual([
      { kind: "text", text: "x " },
      { kind: "cite", id: "S1" },
      { kind: "cite", id: "S12" },
    ]);
  });

  it("leaves text without tokens and lookalikes alone", () => {
    expect(splitCitations("không có [S] hay [s1] hay [SX]")).toEqual([
      { kind: "text", text: "không có [S] hay [s1] hay [SX]" },
    ]);
    expect(splitCitations("")).toEqual([]);
  });
});
