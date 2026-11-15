import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AudioManagement from "./AudioManagement.jsx";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("AudioManagement text-to-speech", () => {
  it("translates the source text and generates audio for each selected language", async () => {
    const fetchMock = vi.fn(async (_url, options = {}) => {
      if (options.method === "POST") {
        return { ok: true, status: 201, json: async () => ({}) };
      }
      if (_url.includes("/api/admin/places?")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            items: [{ PlaceId: 12, PlaceName: "Bưu điện", Slug: "bu-u-dien" }],
          }),
        };
      }
      return { ok: true, status: 200, json: async () => [] };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <AudioManagement
        apiUrl="http://localhost:8000"
        token="admin-token"
        setError={vi.fn()}
        setNotice={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Dịch và tạo audio" })).toBeEnabled();
    });
    fireEvent.change(await screen.findByLabelText("Nội dung thuyết minh *"), {
      target: { value: "Xin chào, đây là bài thuyết minh." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Dịch và tạo audio" }));

    await waitFor(() => {
      expect(fetchMock.mock.calls.filter(([, options]) => options?.method === "POST")).toHaveLength(2);
    });

    const requests = fetchMock.mock.calls
      .filter(([, options]) => options?.method === "POST")
      .map(([, options]) => JSON.parse(options.body));
    expect(requests).toEqual([
      {
        language: "en",
        title: "",
        text: "Xin chào, đây là bài thuyết minh.",
        source_text: "Xin chào, đây là bài thuyết minh.",
        source_language: "vi",
      },
      {
        language: "ko",
        title: "",
        text: "Xin chào, đây là bài thuyết minh.",
        source_text: "Xin chào, đây là bài thuyết minh.",
        source_language: "vi",
      },
    ]);
  });
});
