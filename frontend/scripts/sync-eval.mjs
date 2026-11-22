// pnpm sync-eval: ../eval/results/{retrieval_v1,answers_*,latency}.json -> src/content/eval.json
// Thiếu retrieval_v1.json thì giữ nguyên eval.json (pending) và thoát 0. File hỏng hoặc sai split thì thoát 1, không ghi gì.
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { buildEvalContent } from "./build-eval.mjs";

const results = new URL("../../eval/results/", import.meta.url);
const target = new URL("../src/content/eval.json", import.meta.url);
const read = (u) => JSON.parse(readFileSync(u, "utf8"));

const retrievalFile = new URL("retrieval_v1.json", results);
if (!existsSync(retrievalFile)) {
  console.log(`sync-eval: không có ${fileURLToPath(retrievalFile)}, giữ nguyên eval.json (pending).`);
  process.exit(0);
}
try {
  const answersName = existsSync(results) ? readdirSync(results).filter((f) => /^answers_.*\.json$/.test(f)).sort().at(-1) : undefined;
  const latencyFile = new URL("latency.json", results);
  const content = buildEvalContent(
    read(retrievalFile),
    answersName ? read(new URL(answersName, results)) : undefined,
    existsSync(latencyFile) ? read(latencyFile) : undefined,
    new Date().toISOString(),
  );
  writeFileSync(target, JSON.stringify(content, null, 2) + "\n");
  console.log(`sync-eval: đã ghi ${fileURLToPath(target)} (${content.ablation.length} mode${answersName ? `, ${answersName}` : ""}${content.latency ? ", latency" : ""}).`);
} catch (e) {
  console.error(`sync-eval: ${e.message}`);
  process.exit(1);
}
