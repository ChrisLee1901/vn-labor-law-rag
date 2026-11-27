import { Button } from "@/components/ui/button";

/** Lấy từ eval/golden/v1.jsonl (q039/q067 diễn đạt lại theo năm, q087, q032, q001, q008, q054). */
export const SUGGESTED_QUESTIONS = [
  "Năm 2026, lương tối thiểu tháng vùng I là bao nhiêu?",
  "Từ 1/1/2027, lương tối thiểu tháng vùng I là bao nhiêu?",
  "Công ty sắp họp xử lý kỷ luật tôi. Họ phải báo trước ít nhất mấy ngày, và trong buổi họp tôi có quyền gì?",
  "Vị trí cần bằng cao đẳng trở lên thì thử việc tối đa bao nhiêu ngày?",
  "Vợ sinh thường một bé thì chồng đang đóng BHXH được nghỉ hưởng thai sản mấy ngày?",
  "Hợp đồng 6 tháng và hợp đồng 2 năm thì thời gian báo trước khi nghỉ việc khác nhau thế nào?",
] as const;

export function SuggestedQuestions({ onPick }: { onPick: (q: string) => void }) {
  return (
    <ul aria-label="Câu hỏi gợi ý" className="grid gap-2 sm:grid-cols-2">
      {SUGGESTED_QUESTIONS.map((q) => (
        <li key={q} className="flex">
          <Button
            type="button"
            variant="outline"
            onClick={() => onPick(q)}
            className="h-auto min-h-11 w-full justify-start whitespace-normal py-2 text-left text-sm font-normal leading-snug"
          >
            {q}
          </Button>
        </li>
      ))}
    </ul>
  );
}
