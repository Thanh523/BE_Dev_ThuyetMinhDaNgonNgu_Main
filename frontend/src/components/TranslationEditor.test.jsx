import { useState } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import TranslationEditor from "./TranslationEditor.jsx";

function TranslationEditorHarness({ onChange }) {
  const [translations, setTranslations] = useState({});
  return (
    <TranslationEditor
      apiUrl="http://localhost:8000"
      fields={[{
        key: "place_name",
        label: "Tên địa điểm",
        sourceText: "Bảo tàng Thành phố",
      }]}
      onChange={(value) => {
        setTranslations(value);
        onChange(value);
      }}
      setError={vi.fn()}
      token="admin-token"
      translations={translations}
    />
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("admin translation suggestions", () => {
  it("requests a DeepL suggestion and returns it for review", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ translated_text: "City Museum" }),
    }));
    const onChange = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<TranslationEditorHarness onChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: "Gợi ý dịch bằng DeepL" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/admin/translations/suggest");
    expect(options.method).toBe("POST");
    expect(new Headers(options.headers).get("Authorization")).toBe("Bearer admin-token");
    expect(JSON.parse(options.body)).toEqual({
      text: "Bảo tàng Thành phố",
      source_language: "vi",
      target_language: "en",
    });
    await waitFor(() => {
      expect(onChange).toHaveBeenCalledWith({
        en: { place_name: "City Museum" },
      });
    });
    expect(await screen.findByDisplayValue("City Museum")).toBeInTheDocument();
  });
});
