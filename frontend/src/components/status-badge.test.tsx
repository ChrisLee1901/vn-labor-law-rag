import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { StatusBadge } from "@/components/status-badge";

const fetchMock = vi.fn();

function health(body: unknown, ok = true) {
  fetchMock.mockResolvedValue({ ok, json: async () => body });
}

function setHidden(hidden: boolean) {
  Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
  document.dispatchEvent(new Event("visibilitychange"));
}

// Cho promise của fetch và setState chạy xong.
const flush = () => act(async () => {});

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  setHidden(false);
  fetchMock.mockReset();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("StatusBadge", () => {
  it("llm offline, db ok -> Chế độ ngoại tuyến", async () => {
    health({ llm: "offline", db: "ok", index_version: 1 });
    render(<StatusBadge />);
    await flush();
    expect(screen.getByRole("status")).toHaveTextContent("Chế độ ngoại tuyến");
    expect(fetchMock).toHaveBeenCalledWith("/api/health", expect.anything());
  });

  it("llm online, db ok -> Mô hình trực tuyến", async () => {
    health({ llm: "online", db: "ok", index_version: 1 });
    render(<StatusBadge />);
    await flush();
    expect(screen.getByRole("status")).toHaveTextContent("Mô hình trực tuyến");
  });

  it("db down -> Mất kết nối dữ liệu", async () => {
    health({ llm: "online", db: "down", index_version: 1 });
    render(<StatusBadge />);
    await flush();
    expect(screen.getByRole("status")).toHaveTextContent("Mất kết nối dữ liệu");
  });

  it("fetch lỗi -> Mất kết nối dữ liệu", async () => {
    fetchMock.mockRejectedValue(new Error("network"));
    render(<StatusBadge />);
    await flush();
    expect(screen.getByRole("status")).toHaveTextContent("Mất kết nối dữ liệu");
  });

  it("HTTP không ok -> Mất kết nối dữ liệu", async () => {
    health({ detail: "lỗi" }, false);
    render(<StatusBadge />);
    await flush();
    expect(screen.getByRole("status")).toHaveTextContent("Mất kết nối dữ liệu");
  });

  it("phản hồi không phải JSON -> Mất kết nối dữ liệu", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => {
        throw new SyntaxError("Unexpected token <");
      },
    });
    render(<StatusBadge />);
    await flush();
    expect(screen.getByRole("status")).toHaveTextContent("Mất kết nối dữ liệu");
  });

  it("unmount: hủy request đang chờ và ngừng poll", async () => {
    let signal: AbortSignal | undefined;
    fetchMock.mockImplementation((_url: string, init: RequestInit) => {
      signal = init.signal ?? undefined;
      return new Promise(() => {}); // không bao giờ trả lời
    });
    const { unmount } = render(<StatusBadge />);
    await flush();
    expect(signal?.aborted).toBe(false);

    unmount();
    expect(signal?.aborted).toBe(true);
    await act(() => vi.advanceTimersByTimeAsync(120_000));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("poll mỗi 30 s và tạm dừng khi tab ẩn", async () => {
    health({ llm: "online", db: "ok", index_version: 1 });
    render(<StatusBadge />);
    await flush();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(() => vi.advanceTimersByTimeAsync(30_000));
    expect(fetchMock).toHaveBeenCalledTimes(2);

    setHidden(true);
    await act(() => vi.advanceTimersByTimeAsync(90_000));
    expect(fetchMock).toHaveBeenCalledTimes(2);

    setHidden(false); // quay lại tab: kiểm tra ngay rồi poll tiếp
    await flush();
    expect(fetchMock).toHaveBeenCalledTimes(3);
    await act(() => vi.advanceTimersByTimeAsync(30_000));
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });
});
