# Bộ tài liệu tiếng Việt cho RAG demo: liên kết chéo, tải tự do (trạng thái 22/11/2026)

## Q1. Which official/free sources allow scripted docx/pdf download, and what are the URL patterns?

### Takeaway
**congbao.chinhphu.vn (Công báo) is the best source for scripted downloads.** Each document page is static HTML. It links a text-layer PDF on `congbaocdn.chinhphu.vn` and a `.doc`/`.docx` on `g7.cdnchinhphu.vn`, and robots.txt allows everything. I downloaded real files from it (tested below). vanban.chinhphu.vn is the second choice: it gives direct `datafiles.chinhphu.vn` PDFs, but some are scanned images with no text. vbpl.vn was rebuilt in 2026 as a JS app. Its old attachment URLs now return 404, and files are served through an API, so don't script against it. thuvienphapluat/luatvietnam are commercial sites with anti-bot measures; avoid them.

### Cited Findings
**congbao.chinhphu.vn (recommended)**
- robots.txt is `User-agent: * / Allow: /`. I fetched it on 22/11/2026. — [congbao robots.txt](https://congbao.chinhphu.vn/robots.txt)
- Document page pattern: `https://congbao.chinhphu.vn/van-ban/<slug>-<id>.htm`. The page shows "Ban hành: dd/mm/yyyy - Hiệu lực: dd/mm/yyyy", for example "Ban hành: 26/06/2026 - Hiệu lực: 15/08/2026" for NĐ 238/2026. The HTML holds `href`s to (a) `https://congbaocdn.chinhphu.vn/...pdf` and (b) `https://g7.cdnchinhphu.vn/api/download/stream?Url=<token>&file_name=<name>.doc|.docx|.pdf`. — [NĐ 238/2026 on Công báo](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-238-2026-nd-cp-469913/66580.htm)
- **Tested 22/11/2026 with curl (browser UA):**
  - The NĐ 238/2026 `.docx` stream link returned HTTP 200, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, 65,707 bytes, a valid OOXML file. The extracted text starts "CHÍNH PHỦ … Số: 238/2026/NĐ-CP … Hà Nội, ngày 26 tháng 6 năm 2026". — [page](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-238-2026-nd-cp-469913/66580.htm)
  - The Luật BHXH 41/2024 `.doc` returned HTTP 200, `application/msword`, 884,736 bytes (an OLE Word 97 file). The `congbaocdn` PDF returned HTTP 200, 88 pages, with **253,988 extractable characters**, so it has a text layer. — [Luật 41/2024 on Công báo](https://congbao.chinhphu.vn/van-ban/luat-so-41-2024-qh15-42576.htm)
  - The VBHN 18/VBHN-VPQH (Bộ luật Lao động consolidated) `.docx` was 169,018 bytes, about 190k characters, with 224 "Điều N." headings. VBHN 55/VBHN-VPQH (Luật TTATGTĐB consolidated) `.docx` was about 166k characters. NĐ 374/2025 `.docx` was about 168k characters. — [VBHN 18](https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-18-vbhn-vpqh-468971.htm), [VBHN 55](https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-55-vbhn-vpqh-469185.htm), [NĐ 374/2025](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-374-2025-nd-cp-468724.htm)
  - The `g7` token for the NĐ 238/2026 docx was identical on two fetches about 30 minutes apart. The tokens look deterministic, but expiry over a longer period is untested.
- Format notes: for 2024–2025 documents, Công báo provides `.doc` (Word 97) plus a text PDF of the gazette pages. For 2026 documents it provides `.docx` plus a `_signed.pdf`. Long documents are split across gazette issues, e.g. Luật 36/2024 is in issues 977+978 and 979+980, so you get 2 files per format to concatenate. — [Luật 36/2024 page](https://congbao.chinhphu.vn/van-ban/luat-so-36-2024-qh15-42555.htm)
- Công báo also has a direct "tai-ve" endpoint, e.g. `https://congbao.chinhphu.vn/tai-ve-van-ban-so-45-2019-qh14-30232-29070?format=pdf` for Bộ luật Lao động 2019. Its metadata labels that document "Nghị quyết", which looks like a labelling error. — [search hit](https://congbao.chinhphu.vn/tai-ve-van-ban-so-45-2019-qh14-30232-29070?format=pdf)

**vanban.chinhphu.vn + datafiles.chinhphu.vn**
- robots.txt allows everything. — [vanban robots.txt](https://vanban.chinhphu.vn/robots.txt)
- Page pattern `https://vanban.chinhphu.vn/?pageid=27160&docid=<N>`. The static HTML contains a direct link `https://datafiles.chinhphu.vn/cpp/files/vbpq/<YYYY>/<M>/<file>.pdf`. Tested: docid 212167 → `.../vbpq/2025/01/168-nd-cp.signed.pdf`, docid 218613 → `.../2026/7/238-ndcp.signed.pdf`, docid 214189 → `.../2025/6/158-ndcp.signed.pdf`. — [168/2024](https://vanban.chinhphu.vn/?pageid=27160&docid=212167), [238/2026](https://vanban.chinhphu.vn/?docid=218613&pageid=27160), [158/2025](https://vanban.chinhphu.vn/?docid=214189&pageid=27160)
- **Warning, tested:** `238-ndcp.signed.pdf` (14 pages) and `158-ndcp.signed.pdf` (52 pages) gave only about 190–228 characters from pdftotext, just the digital-signature stamp. They are **scanned images and would need OCR**. By contrast, `399_2026_nd-cp_02112026_6-signed.signed.pdf` (4 pages, HTTP 200, 606,159 bytes) has a full text layer. — [datafiles 399/2026](https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/11/399_2026_nd-cp_02112026_6-signed.signed.pdf), [datafiles 238/2026](https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/7/238-ndcp.signed.pdf)
- The on-site search (`/?pageid=473&q=...`) returned the same 67 KB shell for every query; results load dynamically, so it can't be scripted with plain HTTP. Find docids with a web search instead. — [vanban.chinhphu.vn](https://vanban.chinhphu.vn/)

**vbpl.vn (CSDL quốc gia về pháp luật, Bộ Tư pháp)**
- It is now a Next.js app. Document pages look like `https://vbpl.vn/van-ban/chi-tiet/<slug>--<id>`; the sitemap index has 12 central and many local sub-sitemaps of about 5,000 URLs each, and includes 2026 documents. — [vbpl sitemap](https://vbpl.vn/sitemap.xml)
- robots.txt: `Allow: /`, `Disallow: /api/`, `Disallow: /Pages/`. — [vbpl robots.txt](https://vbpl.vn/robots.txt)
- Old SharePoint attachment URLs that search engines still index now return 404 (tested `https://vbpl.vn/TW/Lists/vbpq/Attachments/179780/157.2025.ND-CP.doc` and `https://vbpl.vn/FileData/TW/Lists/vbpq/Attachments/171147/VanBanGoc_137_2024_ND-CP_23102024_1-signed.pdf`). `vbpl.moj.gov.vn` no longer resolves in DNS.
- The site's JS fetches files client-side from `https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/minio/buckets/vbpl/{documentId}/{fileName}/download` (seen in the public JS bundle). I did **not** call this API; it is undocumented. Use vbpl.vn only by hand, to check "Tình trạng hiệu lực".
- phapluat.gov.vn (the new national law portal) explicitly has `Disallow: /api/legal-documents/download` in robots.txt. — [phapluat.gov.vn robots.txt](https://phapluat.gov.vn/robots.txt)

**Commercial aggregators**
- thuvienphapluat.vn: robots.txt allows everything, but WebFetch got **HTTP 403** (anti-bot). — [thuvienphapluat robots](https://thuvienphapluat.vn/robots.txt), [403 page](https://thuvienphapluat.vn/hoi-dap-phap-luat/cac-doi-tuong-khong-thuoc-pham-vi-bao-ho-quyen-tac-gia-235097.html)
- luatvietnam.vn: one static file downloaded fine (a draft amendment to NĐ 168, `.docx`, 94,826 bytes). — [static3.luatvietnam.vn docx](https://static3.luatvietnam.vn/uploaded/others/2026/04/13/dt-nghi-dinh-sua-nd-168_1304095851.docx)

### Inferences
- Scripted pipeline: (1) keep a hard-coded list of Công báo page URLs (Q3/Q4), (2) GET each page and regex `href="(https://(congbaocdn|g7\.cdnchinhphu)[^"]+)"`, (3) prefer `.docx` > `.doc` > `congbaocdn` PDF, (4) convert `.doc` with LibreOffice `soffice --headless --convert-to docx`, (5) concatenate multi-issue parts, (6) strip gazette headers such as "CÔNG BÁO/Số 979 + 980/Ngày 24-8-2024". I wrote and ran a 25-line `urllib` scraper for this. Its output, a manifest of 16 documents, is at `C:\Users\ADMIN\AppData\Local\Temp\claude\c50d748ff78c9cf8\194e8fee-039b-4479-a7ad-4aa64a3eb893\scratchpad\manifest.json` (temporary folder).
- Prefer re-scraping the page over hard-coding `g7` token URLs, in case the tokens rotate.
- Add a 1–2 s delay between requests and use a descriptive User-Agent. There are only about 20 files, so load is trivial.

### Gaps
- ToS text for congbao/vanban not read; only robots.txt checked.
- Whether thuvienphapluat/luatvietnam need a login for docx was not checked (403 blocked the check).
- Long-term `g7` token expiry is unknown.

## Q2. Are Vietnamese legal normative documents free of copyright, so the corpus can be redistributed?

### Takeaway
Yes. Điều 15 Luật Sở hữu trí tuệ excludes "văn bản quy phạm pháp luật, văn bản hành chính, văn bản khác thuộc lĩnh vực tư pháp và bản dịch chính thức" from copyright protection. Official government copies (Công báo, chinhphu.vn) can be downloaded and bundled with a demo. Commercial annotations, summaries and Q&A on thuvienphapluat/luatvietnam are not covered by that exclusion.

### Cited Findings
- Clause 2 of Article 15 places legal normative documents, administrative documents and judicial documents outside copyright. The stated rationale is that protecting them would contradict the principles of publicity and transparency. — [Luật Minh Khuê](https://luatminhkhue.vn/van-ban-phap-luat-co-duoc-bao-ho-quyen-so-huu-tri-tue-khong.aspx); [TVPL Q&A](https://thuvienphapluat.vn/hoi-dap-phap-luat/doi-tuong-khong-thuoc-pham-vi-bao-ho-quyen-tac-gia-96705.html)
- Original 2005 text of the IP Law (Vietnamese PDF). — [Creative Commons mirror](https://mirrors.creativecommons.org/international/vn/IP-Law-2005-(Vietnamese).pdf)
- A secondary source says Article 15 was amended in 2025, while others cite the 2005 law as amended in 2009. Check the current consolidated text. — [search summary of TVPL/LMK pages](https://thuvienphapluat.vn/hoi-dap-phap-luat/doi-tuong-khong-thuoc-pham-vi-bao-ho-quyen-tac-gia-21491.html)
- The HF dataset th1nhng0/vietnamese-legal-documents states that the underlying documents are public domain under Vietnamese law. It licenses its own compilation as CC BY 4.0. — [HF card](https://huggingface.co/datasets/th1nhng0/vietnamese-legal-documents)

### Inferences
- Bundling Công báo docx/pdf in a public GitHub repo is low-risk. Add a README note citing Điều 15 and linking each source page.

### Gaps
- I did not read the verbatim current (post-2025) Article 15 from a primary source; thuvienphapluat returned 403.

## Q3. Candidate set A, primary: Labor + social insurance + unemployment insurance ("Hồ sơ người lao động")

### Takeaway
This set is about 10 core files, expandable to about 15. All of them are in effect on 22/11/2026, available on Công báo as docx/doc/pdf, and they cite each other densely: decrees cite their parent laws by article, and NĐ 374/2025 cites Luật BHXH, Luật BHYT and Luật Việc làm together. It also supports temporal questions: minimum wage under NĐ 293/2025 (2026) vs NĐ 399/2026 (from 1/1/2027). The main risk: an amendment to Bộ luật Lao động is before the National Assembly now, with proposed effect 1/3/2027.

### Cited Findings
**Core file list** (status = in effect unless noted; P = Công báo page; files = links found on the page and tested where marked)

| # | Number | Title | Issued → effective | Source / files |
|---|---|---|---|---|
| A1 | VBHN 18/VBHN-VPQH (consolidates BLLĐ 45/2019/QH14) | Bộ luật Lao động, consolidated | 12/02/2026; BLLĐ effective 01/01/2021 | P: [congbao 468971](https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-18-vbhn-vpqh-468971.htm) → `.docx` (tested, 169 KB) + `_signed.pdf` |
| A2 | 145/2020/NĐ-CP | Quy định chi tiết BLLĐ về điều kiện lao động và quan hệ lao động | 14/12/2020 → 01/02/2021 | P: [congbao 32732](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-145-2020-nd-cp-32732.htm) → 2× `.doc` + 2× PDF (issues 1203–1206), e.g. [PDF part 1](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2020/12/32732/33806-1-20201203-1204145-2020-nd-cp.pdf) |
| A3 | 293/2025/NĐ-CP | Mức lương tối thiểu đối với NLĐ làm việc theo HĐLĐ (replaces 74/2024) | 10/11/2025 → 01/01/2026; superseded from 01/01/2027 | P: [congbao 46568](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-293-2025-nd-cp-46568.htm) → `.doc` + [PDF](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2025/11/46568/59713-1-20251591-1592293-2025-nd-cp.pdf) |
| A4 | 399/2026/NĐ-CP | Mức lương tối thiểu (new) | 02/11/2026 → 01/01/2027 (signed but not yet in effect) | [datafiles PDF](https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/11/399_2026_nd-cp_02112026_6-signed.signed.pdf), tested, has text layer |
| A5 | 41/2024/QH15 | Luật Bảo hiểm xã hội | 29/06/2024 → main provisions 01/07/2025 | P: [congbao 42576](https://congbao.chinhphu.vn/van-ban/luat-so-41-2024-qh15-42576.htm) → `.doc` (tested 885 KB) + [PDF](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2024/6/42576/51466-1-2024987-98841-2024-qh15.pdf) (tested, 88 pp, text) |
| A6 | 158/2025/NĐ-CP | Hướng dẫn Luật BHXH về BHXH bắt buộc | 25/06/2025 → 01/07/2025 | P: [congbao 45240](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-158-2025-nd-cp-45240.htm) → `.doc` + [PDF](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2025/6/45240/57069-1-2025851-852158-2025-nd-cp.pdf). Avoid the scanned datafiles copy. |
| A7 | 74/2025/QH15 | Luật Việc làm (replaces 2013 law) | 16/06/2025 → 01/01/2026 | P: [congbao 45562](https://congbao.chinhphu.vn/van-ban/luat-so-74-2025-qh15-45562.htm) → `.doc` + [PDF](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2025/6/45562/57700-1-2025967-96874-2025-qh15.pdf) |
| A8 | 374/2025/NĐ-CP | Quy định chi tiết Luật Việc làm về bảo hiểm thất nghiệp | 31/12/2025 → 01/01/2026 | P: [congbao 468724](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-374-2025-nd-cp-468724.htm) → `.docx` (tested, ~168k chars) + PDF |

- Official listings confirm dates and signatories: NĐ 293/2025 on [vanban docid 215832](https://vanban.chinhphu.vn/?pageid=27160&docid=215832), Luật Việc làm and NĐ 145 via the Công báo pages above, NĐ 374 on [vanban docid 216493](https://vanban.chinhphu.vn/?docid=216493&pageid=27160).
- Minimum wage 2026 under NĐ 293/2025: Vùng I 4,960,000 → 5,310,000; Vùng II 4,410,000 → 4,730,000 VND/month; average increase 7.2%. — [luatvietnam](https://luatvietnam.vn/tin-van-ban-moi/chinh-thuc-tang-luong-toi-thieu-vung-cao-nhat-350000-dong-tu-01-01-2026-186-105235-article.html), [EY](https://www.ey.com/vi_vn/technical/tax/tax-and-law-updates/nghi-dinh-293-2025nd-cp-quy-dinh-muc-luong-toi-thieu-doi-voi-nguoi-lao-dong-lam-viec-theo-hop-dong-lao-dong)
- NĐ 399/2026 text (extracted from the PDF I downloaded): monthly / hourly minimum wage is Vùng I 5,700,000 / 27,400; Vùng II 5,080,000 / 24,400; Vùng III 4,450,000 / 21,400; Vùng IV 4,040,000 / 19,400. It cites "Bộ luật Lao động số 45/2019/QH14", "Luật Tổ chức Chính phủ số 63/2025/QH15" and "Luật Tổ chức chính quyền địa phương số 72/2025/QH15", and was issued "Theo đề nghị của Bộ trưởng Bộ Nội vụ". Effective 1/1/2027. — [datafiles PDF](https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/11/399_2026_nd-cp_02112026_6-signed.signed.pdf), [VOV](https://vov.vn/xa-hoi/luong-toi-thieu-vung-tang-tu-112027-post1346877.vov)
- VBHN 18/VBHN-VPQH (text I downloaded) lists BLLĐ 45/2019 as amended by: Luật Công nghiệp công nghệ số 71/2025/QH15 (effective 01/01/2026), Luật Dân số 113/2025/QH15 (effective 01/07/2026), and Luật Giáo dục nghề nghiệp 124/2025/QH15 (effective 01/01/2026). — [VBHN 18](https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-18-vbhn-vpqh-468971.htm)
- NĐ 374/2025 (text I downloaded) explicitly cross-cites "Luật Bảo hiểm xã hội", "khoản 5 Điều 35 Luật Bảo hiểm y tế (được sửa đổi … tại khoản 27 Điều 1 Luật số 51/2024/QH15)" and "Điều 47 Luật Việc làm". — [NĐ 374/2025](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-374-2025-nd-cp-468724.htm)
- NĐ 158/2025: Article 3 covers who must contribute, Article 7 the contribution wage, Article 8 back-payment (calculated per Articles 33–34 of the 2024 BHXH law), and Article 10 suspension of up to 12 months. Probation contracts are excluded from compulsory BHXH. — [MISA AMIS](https://amis.misa.vn/231495/nghi-dinh-158-2025-nd-cp/), [luatvietnam](https://luatvietnam.vn/tin-van-ban-moi/chinh-thuc-hop-dong-thu-viec-khong-phai-dong-bao-hiem-xa-hoi-186-102706-article.html)
- Under Luật Việc làm 2025, the unemployment benefit is 60% of the average BHTN contribution wage over the last 6 months, for up to 12 months. — [pbgdpl Cần Thơ](https://pbgdpl.cantho.gov.vn/quy-dinh-ve-tro-cap-that-nghiep)
- **Pending change (risk):** a bill amending Bộ luật Lao động together with other laws was submitted on 21/10/2026, with proposed effect 01/03/2027. It would add a paid holiday on 24/11 effective on passage, and move labour subleasing from licensing to notification. I found no confirmed final vote as of my searches. — [Đại biểu Nhân dân](https://daibieunhandan.vn/bao-dam-quyen-loi-ich-cua-nguoi-lao-dong-10435012.html), [LSVN](https://lsvn.vn/chinh-phu-de-xuat-bo-sung-1-ngay-nghi-huong-nguyen-luong-vao-bo-luat-lao-dong-a181279.html), [tcnnld](https://tcnnld.vn/news/detail/73794/Trinh-Quoc-hoi-du-an-Luat-sua-doi-bo-sung-mot-so-dieu-cua-Bo-luat-Lao-dong-Luat-Luu-tru-Luat-Binh-dang-gioi-Luat-Hoat-dong-chu-thap-do-va-Luat-Viec-lam.html)
- Bộ Nội vụ 2026 documents propose amending Luật BHXH 2024 and NĐ 158/159/2025 (draft stage). — [quochoi draft PDF](https://gatewayduthaoonline.quochoi.vn/uploadFiles/host/local/2026/6/22/16/389d219178f54d5085b4bfae2092dd78.pdf)

**Optional extensions (URLs not verified on Công báo yet):** Thông tư 12/2025/TT-BNV (30/06/2025, details compulsory BHXH; cited in a Bộ Nội vụ report — [quochoi PDF](https://gatewayduthaoonline.quochoi.vn/uploadFiles/host/local/2025/12/15/9/43c33f0a38864932bcf06a8a813ebec8.pdf)); NĐ 159/2025 (voluntary BHXH); Luật BHYT sửa đổi 51/2024/QH15; VBHN 02/VBHN-BNV on minimum wage ([vanban docid 215936](https://vanban.chinhphu.vn/?pageid=27160&docid=215936&classid=0)); NĐ 138/2026/NĐ-CP (Luật Việc làm, skills development, effective 07/04/2026, per a search summary).

### Inferences
- **Why this works as a demo:** the questions are concrete (thử việc, lương tối thiểu, trợ cấp thất nghiệp, thai sản, chấm dứt HĐLĐ), every answer needs a law plus a decree, and the 2026 vs 2027 minimum wage tests time-aware answers. It also matches an "HR assistant" pitch that recruiters understand.
- Size: about 8 files of 0.1–1 MB, roughly 1.2–1.5M characters, which is fine for chunking and embedding on a laptop or Kaggle.
- To limit staleness, show "effective" metadata per chunk and answer with "theo văn bản hiện hành tại ngày …". If the BLLĐ amendment passes, adding it becomes a good "amended-by" demo.

### Gaps
- Final vote status of the 2026 BLLĐ amendment bill is unconfirmed (Kỳ họp thứ 2, QH khóa XVI, still ongoing).
- Whether NĐ 145/2020 has been partially amended in 2025–2026 is unchecked.
- Công báo page URLs for TT 12/2025/TT-BNV, NĐ 159/2025 and Luật 51/2024 were not collected.
- I did not verify the specific BHXH/BHTN figures (rates, caps) used in the demo questions; take answers from the files themselves.

## Q4. Candidate set B, runner-up: Road traffic (Luật TTATGTĐB 2024 + Luật Đường bộ 2024 + penalty decrees)

### Takeaway
This is the most relatable domain (fines, licence points), with about 10 files on Công báo, all currently in effect. It has a clean "base decree + amending decree" pair: NĐ 168/2024 is amended by NĐ 238/2026 (effective 15/08/2026), and NĐ 165/2024 by NĐ 241/2026 (effective 01/07/2026). That pair is a strong showcase for version-aware RAG, and a trap for naive RAG that quotes outdated fines.

### Cited Findings
| # | Number | Title | Issued → effective | Source / files |
|---|---|---|---|---|
| B1 | 36/2024/QH15 (+ VBHN 55/VBHN-VPQH, 23/03/2026) | Luật Trật tự, an toàn giao thông đường bộ | 27/06/2024 → 01/01/2025 | [congbao 42555](https://congbao.chinhphu.vn/van-ban/luat-so-36-2024-qh15-42555.htm) (2× `.doc` + 2× PDF); consolidated [VBHN 55](https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-55-vbhn-vpqh-469185.htm) `.docx` (tested) |
| B2 | 35/2024/QH15 | Luật Đường bộ | 27/06/2024 → 01/01/2025 | [vanban docid 211193](https://vanban.chinhphu.vn/?pageid=27160&docid=211193) |
| B3 | 151/2024/NĐ-CP | Chi tiết Luật TTATGTĐB | 15/11/2024 → 01/01/2025 | [congbao 43411](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-151-2024-nd-cp-43411.htm) |
| B4 | 165/2024/NĐ-CP | Chi tiết Luật Đường bộ + Điều 77 Luật TTATGTĐB | 26/12/2024 → 01/01/2025 | [congbao 43729](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-165-2024-nd-cp-43729.htm) |
| B5 | 241/2026/NĐ-CP | Sửa đổi NĐ 165/2024 | 26/06/2026 → 01/07/2026 | [congbao 469914](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-241-2026-nd-cp-469914.htm) (`.docx`) |
| B6 | 168/2024/NĐ-CP | Xử phạt VPHC giao thông đường bộ; trừ điểm, phục hồi điểm GPLX | 26/12/2024 → 01/01/2025 | [congbao 43733](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-168-2024-nd-cp-43733/54010.htm) (2× `.doc` + 2× PDF); [vanban](https://vanban.chinhphu.vn/?pageid=27160&docid=212167&classid=1&orggroupid=2) |
| B7 | 238/2026/NĐ-CP | Sửa đổi NĐ 168/2024 | 26/06/2026 → 15/08/2026 | [congbao 469913](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-238-2026-nd-cp-469913/66580.htm) (`.docx` tested) |
| B8 | 12/2025/TT-BCA | Sát hạch, cấp GPLX; GPLX quốc tế | 28/02/2025 → 01/03/2025 (may be superseded, see Gaps) | [congbao 44366](https://congbao.chinhphu.vn/van-ban/thong-tu-so-12-2025-tt-bca-44366/55284.htm) |
| B9 | 160/2024/NĐ-CP | Hoạt động đào tạo và sát hạch lái xe | 18/12/2024 (may be superseded by NĐ 94/2026) | [congbao 43636](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-160-2024-nd-cp-43636.htm) |

- VBHN 55 (text I downloaded) shows Luật 36/2024 amended by Luật số 118/2025/QH15 (amends 10 laws related to an ninh, trật tự), effective 01/07/2026. — [VBHN 55](https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-55-vbhn-vpqh-469185.htm)
- NĐ 238/2026's preamble (docx) cites Luật Xử lý VPHC 15/2012/QH13 as amended through Luật 120/2025/QH15, plus Luật TTATGTĐB 36/2024/QH15 "được sửa đổi…". — [NĐ 238/2026](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-238-2026-nd-cp-469913/66580.htm)
- Example change: from 15/8 (2026), carrying a child without a child safety seat is punished with a "cảnh cáo" (warning). NĐ 238 amends clause 8a Article 20 of NĐ 168 (fine of 12–14 million for certain car violations). — [Hà Tĩnh portal](https://hatinh.gov.vn/vi/bai-viet/chinh-thuc-sua-nghi-dinh-168-cho-tre-em-khong-co-ghe-an-toan-bi-phat-canh-cao-tu-15-8), [TVPL EN page](https://thuvienphapluat.vn/van-ban/EN/Vi-pham-hanh-chinh/Decree-238-2026-ND-CP-amendments-to-Decree-168-2024-ND-CP/726899/tieng-anh.aspx)
- NĐ 100/2019 (old traffic penalties) was fully repealed in 2026; NĐ 336/2025 took effect 1/3/2026 and adjusts some road-infrastructure violations. — [Tuổi Trẻ](https://tuoitre.vn/nhung-luu-y-khi-nghi-dinh-100-ve-xu-phat-giao-thong-bai-bo-2026032816052787.htm), [Hà Tĩnh](https://hatinh.gov.vn/vi/bai-viet/chinh-phu-bai-bo-nghi-dinh-100-xu-phat-vi-pham-giao-thong-tu-ngay-155)

### Inferences
- Best for a public demo audience. Requires an "amendment resolver": tag chunks of NĐ 168 that NĐ 238 overrides, or index only consolidated text. No VBHN of NĐ 168 + 238 was found yet.
- NĐ 168's fine tables are long and repetitive, which makes them harder to chunk than set A.

### Gaps
- Status of TT 108/2026/TT-BCA (same title as TT 12/2025, effective 01/07/2026?) and NĐ 94/2026/NĐ-CP (đào tạo, sát hạch lái xe) seen only in search summaries; they likely replace B8/B9. Check before including.
- VBHN 144/2026/VBHN-LQ-VPQH consolidating Luật Đường bộ (Công báo 528, 25/09/2026) seen only in a search summary; URL not collected.
- NĐ 336/2025 page/URL not collected.

## Q5. Candidate sets C/D: Land law, tax/enterprise, university regulations — status and fit

### Takeaway
Land law is **not recommended**. A comprehensive Luật Đất đai (sửa đổi) is being passed in the Oct–Dec 2026 session, so a corpus built on Luật 31/2024 + NĐ 101/102/103/2024 could be outdated within weeks. Tax/enterprise and university regulations were not researched deeply. Legal domains A/B have more explicit cross-references.

### Cited Findings
- The UBTVQH added Luật Đất đai (sửa đổi) to the 2026 programme for passage at Kỳ họp thứ 2 (October 2026). — [VOV](https://vov.vn/chinh-tri/trinh-quoc-hoi-du-an-luat-dat-dai-tai-ky-hop-cuoi-nam-2026-post1312168.vov), [luatvietnam](https://luatvietnam.vn/tin-van-ban-moi/quoc-hoi-xem-xet-luat-dat-dai-sua-doi-tai-ky-hop-thang-10-2026-186-110407-article.html)
- thuvienphapluat already lists a new "Luật Đất đai" entry (id 716280); content not verified (403). — [TVPL listing](https://thuvienphapluat.vn/van-ban/Bat-dong-san/Luat-Dat-dai-716280.aspx)
- A National Assembly resolution on special mechanisms for implementing Luật Đất đai has applied since 1/1/2026, adding another layer. — [Nhân Dân](https://nhandan.vn/nhieu-thay-doi-quan-trong-trong-chinh-sach-dat-dai-tu-112026-post929465.html)

### Inferences
- If land is still wanted, wait for the new law plus its decrees (probably 2027).
- University regulations (e.g. quy chế đào tạo) have fewer explicit "căn cứ / sửa đổi" links and less stable hosting.

### Gaps
- Final vote on Luật Đất đai (sửa đổi) 2026 is unconfirmed.
- PIT/enterprise-law status in 2026 was not researched (out of time budget).

## Q6. 2025 administrative restructuring: does it make these sets obsolete?

### Takeaway
No. The core laws and decrees in sets A and B remain in effect. Ministry merges changed who issues the documents, not the laws themselves: MOLISA's functions moved to Bộ Nội vụ, and transport moved to Bộ Xây dựng. New 2025–2026 decrees cite the new Luật Tổ chức Chính phủ 63/2025/QH15 and Luật TCCQĐP 72/2025/QH15. Older circulars signed by Bộ LĐTBXH or Bộ GTVT are the ones most at risk of having been replaced.

### Cited Findings
- NĐ 399/2026 was issued "Theo đề nghị của Bộ trưởng Bộ Nội vụ" and cites Luật 63/2025/QH15 and 72/2025/QH15. Its Article 3(3)(d) handles localities that were renamed or split. — [datafiles PDF](https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/11/399_2026_nd-cp_02112026_6-signed.signed.pdf)
- BHXH implementing circular is now TT 12/2025/TT-BNV (Bộ Nội vụ). — [quochoi PDF](https://gatewayduthaoonline.quochoi.vn/uploadFiles/host/local/2025/12/15/9/43c33f0a38864932bcf06a8a813ebec8.pdf)
- 2026 transport-sector circulars are issued by Bộ Xây dựng (e.g. "Thông tư 82/2026/TT-BXD" in the vbpl sitemap; "27-2026-vbhn-bxd" on datafiles). — [vbpl sitemap 1](https://vbpl.vn/sitemap/1.xml), [datafiles](https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/6/27-2026-vbhn-bxd.pdf)

### Inferences
- Skip Thông tư 10/2020/TT-BLĐTBXH unless its effective status is confirmed on vbpl.vn by hand.

### Gaps
- Not verified: TT 10/2020/TT-BLĐTBXH status, and whether NĐ 145/2020 was amended for the 2-tier local government.

## Q7. Hugging Face datasets as an alternative source

### Takeaway
th1nhng0/vietnamese-legal-documents (CC BY 4.0, refreshed 2026-07-23) gives about 171k vbpl.vn documents with effective status and a **1.03M-edge relationship graph**. It is useful for picking related documents or building a graph-RAG extension, but full text comes as HTML (no docx/pdf), and the whole set is 4.37 GB of parquet.

### Cited Findings
- th1nhng0/vietnamese-legal-documents: source vbpl.vn; `metadata` 171,556 rows (17 fields incl. `so_ky_hieu`, `tinh_trang_hieu_luc`); `content` 170,824 rows of `content_html`; `relationships` 1,033,255 edges (amends/cites/repeals); legacy configs with about 518k docs; CC BY 4.0; parquet 4.37 GB; "snapshot, not a live mirror". HF API: license cc-by-4.0, 1M–10M rows, lastModified 2026-08-08, 1,660 downloads. — [HF card](https://huggingface.co/datasets/th1nhng0/vietnamese-legal-documents)
- GreenNode/TVPL-Retrieval-VN: cc-by-sa-4.0, 10K–100K rows, no dataset card. — [HF discussion](https://huggingface.co/datasets/GreenNode/TVPL-Retrieval-VN/discussions/2)
- tmquan/vbpl-vn: the HF API returned no metadata (maybe gated, renamed or removed). An arXiv paper mentions tmquan/thuvienphapluat-vn-* datasets (vbpl 573,851 records). — [HF page](https://huggingface.co/datasets/tmquan/vbpl-vn), [arXiv 2611.11426](https://arxiv.org/pdf/2611.11426)
- Others: thangvip/vietnamese-legal-qa (9,715 docs, 29,145 QA pairs, per search snippet), DuongTrongChi/vi-legal-docs. — [HF](https://huggingface.co/datasets/thangvip/vietnamese-legal-qa/tree/main)

### Inferences
- Use HF datasets for evaluation (QA pairs) or to query the relationship graph for set A's doc IDs. Use Công báo docx/pdf for the "upload real files" demo, since the user wants a folder of docx/pdf.

### Gaps
- Not checked: whether thangvip QA covers the 2024–2026 laws (probably not, given older crawls).

## Q8. Recommendation and sample multi-document demo questions

### Takeaway
**Primary: set A (labor + BHXH + BHTN), 8 core files** (A1–A8), optionally +3–5 extensions for about 12. Reasons: all files are in effect and on Công báo as docx/doc/text-PDF (tested); the documents cite each other explicitly; questions are practical for an HR-assistant demo; and NĐ 293 vs NĐ 399 gives a built-in time-reasoning showcase. **Fallback or second corpus: set B (traffic, 9 files)** for public-facing demos. Its NĐ 168 → NĐ 238 amendment pair showcases version-aware retrieval.

### Cited Findings
- File availability and cross-citations: see Q3/Q4 tables (Công báo pages tested 22/11/2026). — [congbao NĐ 374](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-374-2025-nd-cp-468724.htm), [congbao Luật 41/2024](https://congbao.chinhphu.vn/van-ban/luat-so-41-2024-qh15-42576.htm)

### Inferences
Sample demo questions for set A. Expected source documents are in brackets; answers are not pre-verified.
1. Hợp đồng thử việc có phải đóng BHXH bắt buộc không? [Luật BHXH 41/2024 + NĐ 158/2025 + BLLĐ (thử việc)]
2. Công ty ở địa bàn vùng I trả 5,5 triệu đồng/tháng cho nhân viên toàn thời gian: có vi phạm năm 2026 không, và từ 1/1/2027 thì sao? [BLLĐ (lương tối thiểu) + NĐ 293/2025 + NĐ 399/2026]
3. Mức lương tối thiểu giờ vùng II từ 1/1/2027 là bao nhiêu, tăng bao nhiêu so với 2026, và văn bản nào bị thay thế? [NĐ 293/2025 + NĐ 399/2026]
4. Doanh nghiệp có chi nhánh ở địa bàn khác vùng với trụ sở thì áp dụng lương tối thiểu vùng nào? [NĐ 293/2025 hoặc 399/2026 Điều 3 + BLLĐ]
5. Tôi đóng BHTN 3 năm rồi nghỉ việc: điều kiện, mức và thời gian hưởng trợ cấp thất nghiệp? [Luật Việc làm 74/2025 + NĐ 374/2025]
6. Mức trợ cấp thất nghiệp tối đa mỗi tháng được tính dựa trên mức lương tối thiểu vùng nào, cụ thể bao nhiêu tiền năm 2026? [Luật Việc làm + NĐ 374/2025 + NĐ 293/2025]
7. Nếu tự ý nghỉ việc không báo trước (đơn phương chấm dứt HĐLĐ trái luật) thì có được hưởng trợ cấp thất nghiệp không? [BLLĐ (chấm dứt HĐLĐ) + Luật Việc làm]
8. Khi tính trợ cấp thôi việc, thời gian đã đóng BHTN có bị trừ ra không? [BLLĐ Điều 46 + NĐ 145/2020 + Luật Việc làm]
9. Người sử dụng lao động chậm hoặc trốn đóng BHXH thì bị xử lý thế nào, và NLĐ có bị ảnh hưởng quyền hưởng trợ cấp thất nghiệp không? [Luật BHXH + NĐ 158/2025 + NĐ 374/2025]
10. Tiền lương làm căn cứ đóng BHXH bắt buộc gồm những khoản nào và có được thấp hơn lương tối thiểu vùng không? [Luật BHXH + NĐ 158/2025 + NĐ 293/2025]
11. Lao động nữ được nghỉ thai sản bao lâu và mức hưởng chế độ thai sản tính thế nào? [BLLĐ + Luật BHXH 2024]
12. Từ 1/7/2025 chủ hộ kinh doanh có đăng ký kinh doanh có phải tham gia BHXH bắt buộc không? [Luật BHXH 2024 + NĐ 158/2025]
13. Doanh nghiệp được hỗ trợ kinh phí đào tạo, bồi dưỡng kỹ năng nghề để duy trì việc làm cho NLĐ trong trường hợp nào? [Luật Việc làm + NĐ 374/2025]
14. Hồ sơ hưởng trợ cấp thất nghiệp đã nộp trước 1/1/2026 thì áp dụng quy định cũ hay mới? [NĐ 374/2025 điều khoản chuyển tiếp + Luật Việc làm 2025]
15. Số giờ làm thêm tối đa trong năm là bao nhiêu và ngành nghề nào được làm thêm đến 300 giờ? [BLLĐ + NĐ 145/2020]
16. Bộ luật Lao động 2019 hiện đã được sửa đổi bởi những luật nào và văn bản hợp nhất mới nhất là số mấy? [VBHN 18/VBHN-VPQH]
17. Mức đóng BHTN của NLĐ và NSDLĐ theo Luật Việc làm 2025 là bao nhiêu và tổng tỷ lệ trích đóng BHXH + BHTN là bao nhiêu? [Luật Việc làm + Luật BHXH]
18. NLĐ ký HĐLĐ 1 tháng có phải đóng BHXH và BHTN không? [Luật BHXH 2024 + Luật Việc làm 2025 + BLLĐ (loại HĐLĐ)]
19. Doanh nghiệp được tạm dừng đóng vào quỹ hưu trí, tử tuất trong trường hợp nào và tối đa bao lâu? [Luật BHXH + NĐ 158/2025 Điều 10]
20. Nghị định 374/2025 dẫn chiếu những điều nào của Luật BHXH và Luật BHYT, và vì sao? [NĐ 374/2025 + Luật BHXH + (Luật BHYT if added)]

Sample questions for set B (fallback):
21. Xe máy vượt đèn đỏ bị phạt bao nhiêu và bị trừ mấy điểm GPLX; mức này có thay đổi sau 15/8/2026 không? [NĐ 168/2024 + NĐ 238/2026]
22. GPLX có tối đa bao nhiêu điểm, bị trừ hết điểm thì xử lý thế nào và khi nào được phục hồi điểm? [Luật 36/2024 + NĐ 168/2024 (+238)]
23. Chở trẻ em dưới 10 tuổi trên ô tô không dùng thiết bị an toàn bị xử lý thế nào từ 15/8/2026? [Luật 36/2024 + NĐ 238/2026]
24. Luật Trật tự, an toàn giao thông đường bộ đã được sửa đổi bởi luật nào, hiệu lực từ ngày nào? [VBHN 55 + Luật 118/2025]
25. Nghị định nào hướng dẫn Điều 77 Luật TTATGTĐB và nó đã được sửa đổi năm 2026 ra sao? [NĐ 165/2024 + NĐ 241/2026 + Luật 36/2024]

### Gaps
- Answers to questions 1–25 are not pre-verified. Build a gold answer set from the downloaded texts before demoing.
- The figures that questions 6 and 17 ask about (benefit caps, contribution rates) come from articles I did not read.
