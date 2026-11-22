import { describe, expect, it } from "vitest";
import { DETAIL, DOCS } from "@/mocks/docs";
import { articleAnchor, DOC_TYPE_LABEL, groupByChapter, isValidDocCode, sortDocs } from "./docs-view";
import { DOC_TYPES } from "./api-types";

const NOW = new Date(2026, 10, 22);

describe("DOC_TYPE_LABEL", () => {
  it("covers every doc type in Vietnamese", () => {
    expect(Object.keys(DOC_TYPE_LABEL).sort()).toEqual([...DOC_TYPES].sort());
    expect(DOC_TYPE_LABEL.bo_luat).toBe("Bộ luật");
    expect(DOC_TYPE_LABEL.vbhn).toBe("Văn bản hợp nhất");
  });
});

describe("sortDocs", () => {
  it("puts effective docs first, then future, then expired, newest first within a group", () => {
    expect(sortDocs(DOCS, NOW).map((d) => d.code)).toEqual(["BLLD", "ND399-2026", "ND145-2020"]);
  });
  it("orders by effective_from desc inside a group and does not mutate input", () => {
    const a = { ...DOCS[2], code: "A", effective_from: "2022-01-01" };
    const b = { ...DOCS[2], code: "B", effective_from: "2024-01-01" };
    const input = [a, b];
    expect(sortDocs(input, NOW).map((d) => d.code)).toEqual(["B", "A"]);
    expect(input.map((d) => d.code)).toEqual(["A", "B"]);
  });
});

describe("groupByChapter", () => {
  it("groups consecutive Điều by chapter and leaves appendices out", () => {
    const g = groupByChapter(DETAIL.articles);
    expect(g.map((x) => [x.chapter, x.articles.map((a) => a.id)])).toEqual([
      ["Chương I. Quy định chung", ["ND145-2020:D1", "ND145-2020:D12"]],
      ["Chương II. Tiền lương", ["ND145-2020:D12a", "ND145-2020:D20"]],
    ]);
  });
  it("keeps a null-chapter group", () => {
    const g = groupByChapter([{ ...DETAIL.articles[0], chapter: null }, { ...DETAIL.articles[1], chapter: null }]);
    expect(g).toHaveLength(1);
    expect(g[0].chapter).toBeNull();
  });
});

describe("articleAnchor", () => {
  it("matches the #D{n} / #PL{n} anchors that chat sources link to", () => {
    const ids = DETAIL.articles.map(articleAnchor);
    expect(ids).toEqual(["D1", "D12", "D12a", "D20", "PL1"]);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("isValidDocCode", () => {
  it("accepts fixed codes and rejects anything else", () => {
    for (const c of ["BLLD", "ND145-2020", "LBHXH-2024"]) expect(isValidDocCode(c)).toBe(true);
    for (const c of ["", "a/b", "..", "a b", "ND145_2020", "a?x=1", "Điều"]) expect(isValidDocCode(c)).toBe(false);
  });
});
