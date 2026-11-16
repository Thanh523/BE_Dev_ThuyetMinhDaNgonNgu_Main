import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import NarrationManagement from "./NarrationManagement.jsx";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("NarrationManagement audio selection", () => {
  it("filters the narration list by the selected language", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (url.includes("/api/admin/places?")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            items: [{ PlaceId: 12, PlaceName: "Bưu điện" }],
          }),
        };
      }
      if (url.endsWith("/api/admin/narration-languages")) {
        return {
          ok: true,
          status: 200,
          json: async () => [
            { LanguageCode: "en", LanguageName: "English" },
            { LanguageCode: "vi", LanguageName: "Tiếng Việt" },
          ],
        };
      }
      if (url.endsWith("/api/admin/places/12/narrations")) {
        return {
          ok: true,
          status: 200,
          json: async () => [
            { NarrationId: 1, LanguageCode: "en", Title: "Post Office", Content: "English narration" },
            { NarrationId: 2, LanguageCode: "vi", Title: "Bưu điện tiếng Việt", Content: "Thuyết minh tiếng Việt" },
          ],
        };
      }
      return { ok: true, status: 200, json: async () => [] };
    }));

    render(
      <NarrationManagement
        apiUrl="http://localhost:8000"
        token="admin-token"
        setError={vi.fn()}
        setNotice={vi.fn()}
      />,
    );

    expect(await screen.findByText("Post Office")).toBeInTheDocument();
    expect(screen.getByText("Bưu điện tiếng Việt")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Lọc theo ngôn ngữ"), {
      target: { value: "vi" },
    });

    expect(screen.getByText("Bưu điện tiếng Việt")).toBeInTheDocument();
    expect(screen.queryByText("Post Office")).not.toBeInTheDocument();
  });

  it("fills narration content from the selected generated audio", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (url.includes("/api/admin/places?")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            items: [{ PlaceId: 12, PlaceName: "Bưu điện" }],
          }),
        };
      }
      if (url.endsWith("/api/admin/narration-languages")) {
        return {
          ok: true,
          status: 200,
          json: async () => [{ LanguageCode: "vi", LanguageName: "Tiếng Việt" }],
        };
      }
      if (url.endsWith("/api/admin/places/12/audios")) {
        return {
          ok: true,
          status: 200,
          json: async () => [{
            AudioId: "generated-audio",
            Language: "vi",
            Title: "Audio tiếng Việt",
            SourceText: "Nội dung gốc",
            TranslatedText: "Nội dung audio tiếng Việt",
          }],
        };
      }
      return { ok: true, status: 200, json: async () => [] };
    }));

    render(
      <NarrationManagement
        apiUrl="http://localhost:8000"
        token="admin-token"
        setError={vi.fn()}
        setNotice={vi.fn()}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Thêm nội dung" }));
    await screen.findByRole("option", { name: /Audio tiếng Việt/ });
    fireEvent.change(screen.getByLabelText("Audio"), {
      target: { value: "generated-audio" },
    });

    await waitFor(() => {
      expect(screen.getByLabelText("Nội dung")).toHaveValue("Nội dung audio tiếng Việt");
    });
  });

  it("does not erase content when the selected uploaded audio has no transcript", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (url.includes("/api/admin/places?")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            items: [{ PlaceId: 12, PlaceName: "Bưu điện" }],
          }),
        };
      }
      if (url.endsWith("/api/admin/narration-languages")) {
        return {
          ok: true,
          status: 200,
          json: async () => [{ LanguageCode: "vi", LanguageName: "Tiếng Việt" }],
        };
      }
      if (url.endsWith("/api/admin/places/12/audios")) {
        return {
          ok: true,
          status: 200,
          json: async () => [{
            AudioId: "uploaded-audio",
            Language: "vi",
            Title: "Audio tải lên",
            SourceText: "",
            TranslatedText: "",
          }],
        };
      }
      return { ok: true, status: 200, json: async () => [] };
    }));

    render(
      <NarrationManagement
        apiUrl="http://localhost:8000"
        token="admin-token"
        setError={vi.fn()}
        setNotice={vi.fn()}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Thêm nội dung" }));
    fireEvent.change(screen.getByLabelText("Nội dung"), {
      target: { value: "Nội dung đã nhập" },
    });
    fireEvent.change(screen.getByLabelText("Audio"), {
      target: { value: "uploaded-audio" },
    });

    expect(screen.getByLabelText("Nội dung")).toHaveValue("Nội dung đã nhập");
    expect(screen.getByText(/chưa có nội dung văn bản để tự điền/)).toBeInTheDocument();
  });
});
