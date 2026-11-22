import type { AblationRow, EvalContent } from "@/content/eval-types";

const MODE_LABEL: Record<string, string> = {
  fts: "FTS (từ khóa, như chế độ ngoại tuyến)",
  dense: "Chỉ vector",
  hybrid: "Hybrid RRF",
  hybrid_rerank: "Hybrid RRF + rerank",
};
const ABLATION_COLS: [keyof Omit<AblationRow, "mode">, string][] = [
  ["hit_rate_at_1", "Hit@1"],
  ["recall_at_5", "Recall@5"],
  ["recall_at_10", "Recall@10"],
  ["recall_at_20", "Recall@20"],
  ["mrr_at_10", "MRR@10"],
  ["ndcg_at_10", "nDCG@10"],
];
const ANSWER_ROWS = [
  ["citation_precision", "Độ chính xác trích dẫn"],
  ["citation_recall", "Độ phủ trích dẫn"],
  ["numeric_match", "Khớp số liệu"],
  ["refusal_accuracy", "Từ chối đúng"],
  ["injection_resisted", "Chống prompt injection"],
] as const;
const RETRIEVAL_GLOSSARY: [string, string][] = [
  ["Hit@1", "Tỷ lệ câu hỏi có Điều đúng ở vị trí đầu tiên."],
  ["Recall@k", "Tỷ lệ Điều đúng (gold) nằm trong k kết quả đầu, tính trung bình trên các câu hỏi."],
  ["MRR@10", "Trung bình của 1/hạng của Điều đúng đầu tiên trong 10 kết quả đầu (0 nếu không có)."],
  ["nDCG@10", "Chất lượng xếp hạng trong 10 kết quả đầu, Điều đúng càng cao càng được tính nhiều."],
];
// Định nghĩa dưới đây là tạm, chỉ hiện khi kết quả tương ứng có thật. Task 6.4 (answer_eval) phải đối chiếu lại tên chỉ số và cách tính.
const ANSWER_GLOSSARY: [string, string][] = [
  ["Trích dẫn", "Độ chính xác: trong các [S#] câu trả lời nêu ra, bao nhiêu trỏ đúng Điều gold. Độ phủ: bao nhiêu Điều gold được trích."],
  ["Khớp số liệu", "Con số trong câu trả lời (thời hạn, mức tiền, tỷ lệ) trùng với đáp án trong bộ câu hỏi."],
  ["Từ chối đúng", "Tỷ lệ câu không có căn cứ trong văn bản hoặc ngoài phạm vi mà hệ thống từ chối thay vì bịa."],
  ["Chống injection", "Tỷ lệ câu chứa chỉ dẫn độc hại mà hệ thống không làm theo."],
];
const LATENCY_GLOSSARY: [string, string][] = [
  ["TTFT, p50, p95", "TTFT là thời gian tới token đầu tiên. p50 là trung vị, p95 là mốc mà 95% lượt hỏi nhanh hơn."],
];

const f3 = (n: number) => n.toFixed(3);
const f2s = (n: number) => `${n.toFixed(2)} s`;

type Row = { key: string; header: string; cells: string[] };

function Table({ caption, head, rows }: { caption: string; head: string[]; rows: Row[] }) {
  return (
    <div
      role="region"
      aria-label={`${caption} (cuộn ngang trên màn hình nhỏ)`}
      tabIndex={0}
      className="overflow-x-auto focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
    >
      <table className="w-full min-w-[32rem] border-collapse text-sm tabular-nums">
        <caption className="pb-2 text-left font-medium">{caption}</caption>
        <thead>
          <tr className="border-b text-left">
            {head.map((h, i) => (
              <th key={h} scope="col" className={i ? "px-3 py-2 text-right font-medium" : "py-2 pr-3 font-medium"}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className="border-b">
              <th scope="row" className="py-2 pr-3 text-left font-normal">
                {r.header}
              </th>
              {r.cells.map((c, i) => (
                <td key={i} className="px-3 py-2 text-right">
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function EvalResults({ content }: { content: EvalContent }) {
  const ready = content.status === "ready" ? content : null;
  const glossary = [...RETRIEVAL_GLOSSARY, ...(ready?.answers ? ANSWER_GLOSSARY : []), ...(ready?.latency ? LATENCY_GLOSSARY : [])];
  return (
    <div className="space-y-6">
      {ready ? (
        <>
          <p className="max-w-[var(--measure)] text-muted-foreground">
            Chỉ số tính trên split test của bộ câu hỏi vàng, mỗi bảng ghi số câu của chính nó
            {ready.model ? `. Mô hình sinh câu trả lời: ${ready.model}` : ""}
            {ready.generatedAt ? `. Ngày chạy: ${ready.generatedAt.slice(0, 10)}` : ""}.
          </p>
          {ready.ablation.length ? (
            <div className="space-y-2">
              <Table
                caption={`Ablation truy xuất (cấp Điều): ${ready.retrieval.n_queries} câu có đáp án (gold) trong split test`}
                head={["Chế độ", ...ABLATION_COLS.map(([, l]) => l)]}
                rows={ready.ablation.map((r) => ({ key: r.mode, header: MODE_LABEL[r.mode] ?? r.mode, cells: ABLATION_COLS.map(([k]) => f3(r[k])) }))}
              />
              {ready.ablation.some((r) => r.mode === "hybrid_rerank") && (
                <p className="text-sm text-muted-foreground">
                  Dòng rerank chỉ trả tối đa 6 Điều cha (đúng như API), nên Recall@10 và Recall@20 của dòng này xấp xỉ Recall@6, không so trực tiếp với các dòng khác.
                </p>
              )}
            </div>
          ) : null}
          {ready.answers && (
            <Table
              caption={`Chất lượng câu trả lời: ${ready.answers.n_queries} câu trong split test`}
              head={["Chỉ số", "Giá trị"]}
              rows={ANSWER_ROWS.map(([k, label]) => ({ key: k, header: label, cells: [f3(ready.answers![k])] }))}
            />
          )}
          {ready.latency && (
            <Table
              caption={`Độ trễ: ${ready.latency.n_queries} câu trong split test`}
              head={["Đo", "p50", "p95"]}
              rows={[
                { key: "ttft", header: "Token đầu tiên (TTFT)", cells: [f2s(ready.latency.ttft_p50_s), f2s(ready.latency.ttft_p95_s)] },
                { key: "total", header: "Cả câu trả lời", cells: [f2s(ready.latency.total_p50_s), f2s(ready.latency.total_p95_s)] },
              ]}
            />
          )}
        </>
      ) : (
        <p role="note" className="max-w-[var(--measure)] rounded-md border bg-muted p-4 text-muted-foreground">
          Kết quả đánh giá sẽ được công bố sau lần chạy đầu tiên khi mô hình trực tuyến.
        </p>
      )}

      <div className="space-y-2">
        <h3 className="text-base">Phương pháp</h3>
        <ul className="max-w-[var(--measure)] list-disc space-y-1 pl-5">
          <li>Bộ câu hỏi vàng gồm 120 câu: 42 câu một nguồn, 18 câu số liệu, 18 câu nhiều bước, 12 câu so sánh, 6 câu theo thời điểm, 12 câu thiếu căn cứ trong văn bản, 6 câu ngoài phạm vi và 6 câu prompt injection (ba nhóm sau có đáp án đúng là từ chối).</li>
          <li>Chia dev 40 câu và test 80 câu. Ngưỡng từ chối và prompt chỉnh trên dev, số liệu chỉ công bố trên test.</li>
          <li>Câu hỏi và nhãn do Claude sinh, rồi các lượt Claude khác trả lời mù để kiểm chéo, câu nào không khớp bị loại. Người thật kiểm 20 câu ngẫu nhiên: chưa có người kiểm, đang chờ.</li>
          <li>Truy xuất chấm ở cấp Điều (gold rút về Điều cha), bằng ranx, và chạy trên mỗi PR như một cổng chặn hồi quy.</li>
        </ul>
      </div>

      <div className="space-y-2">
        <h3 className="text-base">Cách đọc các chỉ số</h3>
        <dl className="max-w-[var(--measure)] space-y-2 text-sm">
          {glossary.map(([t, d]) => (
            <div key={t}>
              <dt className="inline font-medium">{t}: </dt>
              <dd className="inline text-muted-foreground">{d}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
