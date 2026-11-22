"""Che thông tin cá nhân trước khi ghi trace (chỉ dùng ở app.tracing: input/output của `chat` và comment feedback gửi Langfuse).

Không đổi gì với văn bản hiển thị cho người dùng hay dữ liệu lưu local (bảng `feedback` giữ comment gốc).
"""

import re

MASK = "[đã ẩn]"
_EMAIL = r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
# Số có dấu phân cách [ .-] chỉ khớp theo nhóm điện thoại (đầu số 0 hoặc +84, nhóm 3-3-3/4), không bắt đầu ngay sau "<số><dấu cách>",
# nên không nuốt số tiền (5.310.000, 12.000.000.000, 1 000 000 000), ngày (01/01/2026, 01-01-2026) hay số hiệu văn bản.
# shortcut: số điện thoại đứng ngay sau một con số + dấu cách ("2020 0912 345 678") không được che; khi nào cần thì siết bằng danh sách đầu số.
_NOT_AFTER_NUM = r"(?<!\d)(?<!\d[ .-])"
_PHONE = rf"{_NOT_AFTER_NUM}(?:\+84[ .-]?\d{{2,3}}|0\d{{2,3}})[ .-]?\d{{3}}[ .-]?\d{{3,4}}(?![ -]\d{{3}})(?!\d)"
_ID = r"(?<!\d)(?:\d{12}|\d{9})(?!\d)"  # CCCD 12 số, CMND 9 số liền
# Dạng tách nhóm bằng dấu cách hoặc gạch (không dùng dấu chấm: đó là dấu ngăn nghìn của tiền), trừ khi theo sau là đơn vị tiền.
_ID_SEP = rf"{_NOT_AFTER_NUM}\d{{3}}(?:[ -]\d{{3}}){{2,3}}(?![ -]\d{{3}})(?!\d)(?!\s*(?:đồng|đ\b|VND|VNĐ))"
_PII = re.compile(f"{_EMAIL}|{_PHONE}|{_ID}|{_ID_SEP}")


def redact_pii(s: str) -> str:
    return _PII.sub(MASK, s)
