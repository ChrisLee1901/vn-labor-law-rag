import type { Metadata } from "next";
import Link from "next/link";
import { ArchitectureDiagram } from "@/components/about/architecture-diagram";
import { EvalResults } from "@/components/about/eval-results";
import evalJson from "@/content/eval.json";
import type { EvalContent } from "@/content/eval-types";
import { cn, focusRing } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Giới thiệu",
  description: "Mục tiêu, kiến trúc, cách đánh giá và giới hạn của Trợ lý Pháp luật Lao động.",
};

const link = cn("underline underline-offset-4 hover:text-foreground", focusRing);
const prose = "max-w-[var(--measure)]";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-xl">{title}</h2>
      {children}
    </section>
  );
}

function List({ children }: { children: React.ReactNode }) {
  return <ul className={cn(prose, "list-disc space-y-1.5 pl-5")}>{children}</ul>;
}

export default function AboutPage() {
  const repoUrl = process.env.NEXT_PUBLIC_REPO_URL;
  return (
    <div className="space-y-10">
      <header className="space-y-2">
        <h1 className="text-2xl sm:text-3xl">Giới thiệu</h1>
        <p className={cn(prose, "text-muted-foreground")}>
          Trợ lý trả lời câu hỏi về pháp luật lao động, bảo hiểm xã hội và bảo hiểm thất nghiệp Việt Nam, mỗi câu trả lời dẫn tới Điều, Khoản cụ thể.
        </p>
      </header>

      <Section title="Mục tiêu">
        <p className={prose}>
          Đây là dự án portfolio: chứng minh người làm tự dựng được một hệ RAG end-to-end, từ xử lý văn bản, truy xuất, tự host mô hình tới đánh giá và CI/CD, thay vì chỉ gọi một API có sẵn.
        </p>
        <List>
          <li>Hỏi đáp tiếng Việt trên 8 văn bản lao động, BHXH và BHTN, có trích dẫn Điều, Khoản.</li>
          <li>Câu trả lời chỉ sinh bằng mô hình open-weight tự host, không gọi API của Gemini, OpenAI hay Claude.</li>
          <li>Khi mô hình tắt, trang vẫn dùng được để tra cứu văn bản.</li>
          <li>Chất lượng đo bằng số liệu trên bộ câu hỏi riêng, không dựa vào cảm giác.</li>
        </List>
      </Section>

      <Section title="Kiến trúc">
        <ArchitectureDiagram />
        <List>
          <li>
            <strong>Hybrid trong pgvector:</strong> tìm theo từ khóa (tsvector) và theo vector (1024 chiều) trong cùng một hàm SQL, hợp nhất bằng Reciprocal Rank Fusion, lấy 40 ứng viên.
          </li>
          <li>
            <strong>Rerank:</strong> mô hình xếp hạng lại chấm ứng viên, giữ 6 Điều cha. Nếu điểm cao nhất dưới ngưỡng, hệ thống từ chối và không gọi LLM.
          </li>
          <li>
            <strong>Chia đoạn theo cấu trúc:</strong> Điều là đoạn cha, Khoản là đoạn con (tối đa 450 token) kèm đường dẫn chương và Điều để embedding hiểu ngữ cảnh.
          </li>
          <li>
            <strong>Mở rộng tham chiếu:</strong> khi một Điều viện dẫn Điều khác, hệ thống kéo thêm đoạn được viện dẫn (một bước, tối đa 4 đoạn).
          </li>
          <li>
            <strong>Kiểm tra trích dẫn bằng mã:</strong> sau khi sinh, mã xác định (không phải LLM) kiểm tra câu trả lời chỉ trích các nguồn đã cung cấp và số Điều khớp tiêu đề nguồn.
          </li>
        </List>
      </Section>

      <Section title="Vì sao tự host LLM trên Kaggle">
        <p className={prose}>Lý do: GPU miễn phí (T4 x2) đủ chạy Qwen3-8B, và tự vận hành mô hình mới là phần kỹ thuật dự án muốn chứng minh. Đánh đổi thì có thật:</p>
        <List>
          <li>Phiên Kaggle tối đa 12 giờ và hạn mức GPU khoảng 30 giờ mỗi tuần, nên mô hình không chạy 24/7. Khởi động mất vài phút.</li>
          <li>Qwen3-8B lượng tử hóa nhỏ hơn nhiều so với các mô hình thương mại, có thể trả lời sai hoặc diễn đạt kém hơn.</li>
          <li>
            Điều khoản Kaggle cấm dùng notebook làm máy chủ chạy liên tục (&quot;server farming&quot;). Dự án chỉ bật notebook trước buổi demo, xác thực bằng token và không công khai địa chỉ tunnel, nhưng cách dùng này vẫn có thể bị Kaggle coi là
            vi phạm. Nó phù hợp cho demo, không phù hợp cho sản phẩm thật.
          </li>
        </List>
      </Section>

      <Section title="Chế độ ngoại tuyến">
        <p className={prose}>Khi notebook Kaggle tắt, huy hiệu trạng thái ở đầu trang chuyển sang ngoại tuyến. Những gì vẫn dùng được:</p>
        <List>
          <li>Tìm theo từ khóa và tra cứu theo số hiệu, Điều, Khoản (không cần embedding): trả danh sách Điều liên quan để đọc trực tiếp.</li>
          <li>Câu hỏi trùng câu mẫu nhận câu trả lời đã lưu từ lần chạy trực tuyến, có nhãn rõ.</li>
          <li>
            Trang <Link href="/van-ban" className={link}>Văn bản</Link> đọc toàn văn từng Điều.
          </li>
        </List>
        <p className={cn(prose, "text-muted-foreground")}>Không làm được khi ngoại tuyến: câu trả lời tổng hợp mới, tìm theo vector và xếp hạng lại.</p>
      </Section>

      <Section title="Kết quả đánh giá">
        <EvalResults content={evalJson as EvalContent} />
      </Section>

      <Section title="Giới hạn đã biết">
        <List>
          <li>Văn bản được tải một lần, không tự cập nhật, nên có thể đã lỗi thời. Hãy đối chiếu bản chính thức trên Công báo.</li>
          <li>Bộ luật Lao động đang chờ sửa đổi, nội dung có thể thay đổi. Nghị định 399/2026 chưa có hiệu lực tại thời điểm viết, hệ thống phân biệt theo ngày hỏi nhưng chỉ cho các văn bản trong kho.</li>
          <li>Kho chưa có phụ lục danh mục địa bàn vùng I-IV của Nghị định 399/2026 (bản đã công bố chỉ có phần thân). Từ 01/01/2027 hệ thống chưa tra được địa bàn thuộc vùng nào, hãy xem phụ lục trên Công báo.</li>
          <li>Đây là thông tin tham khảo, không phải tư vấn pháp lý.</li>
          <li>Mô hình ngôn ngữ có thể sai, kể cả khi có trích dẫn. Hãy bấm vào nguồn và đọc lại điều luật.</li>
          <li>Bộ câu hỏi vàng do Claude sinh và kiểm chéo, có thể chung thiên lệch và chưa phải nhãn của chuyên gia luật. Bộ chỉ có 120 câu trên 8 văn bản, nên chênh lệch nhỏ giữa các chế độ có thể không có ý nghĩa.</li>
          <li>Câu trả lời chưa có người chấm. Các chỉ số trích dẫn và số liệu chỉ do mã chấm, không đánh giá được câu trả lời diễn đạt tốt hay không.</li>
        </List>
      </Section>

      <Section title="Mã nguồn và tài liệu">
        <List>
          {repoUrl ? (
            <li>
              <a href={repoUrl} target="_blank" rel="noreferrer" className={link}>
                Mã nguồn trên GitHub<span className="sr-only"> (mở tab mới)</span>
              </a>
            </li>
          ) : null}
          <li>
            Toàn văn các văn bản dùng làm căn cứ: <Link href="/van-ban" className={link}>Văn bản pháp luật</Link>.
          </li>
          <li>Bộ câu hỏi vàng v1 (120 câu, kèm thẻ dữ liệu mô tả cách sinh, kiểm chéo và hạn chế) nằm trong thư mục eval/golden của kho mã.</li>
          <li>
            Nguồn dữ liệu: bản gốc tải từ <a href="https://congbao.chinhphu.vn" target="_blank" rel="noreferrer" className={link}>congbao.chinhphu.vn<span className="sr-only"> (mở tab mới)</span></a>. Theo Điều 15 Luật Sở hữu trí tuệ, văn bản quy phạm pháp luật không thuộc đối tượng
            bảo hộ quyền tác giả nên được đưa vào kho mã. Chú giải và hỏi đáp của các trang thương mại không dùng.
          </li>
        </List>
      </Section>
    </div>
  );
}
