import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import UserDemo from "./UserDemo.jsx";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("guest place browsing", () => {
  it("loads public places and details, and never records guest listening history", async () => {
    const fetchMock = vi.fn(async (input, options = {}) => {
      const { pathname } = new URL(String(input));
      let payload;

      if (pathname === "/api/user/categories") {
        payload = [{ CategoryId: 3, CategoryName: "Bảo tàng" }];
      } else if (pathname === "/api/user/places") {
        payload = {
          items: [{
            PlaceId: 1,
            PlaceName: "Bảo tàng Thành phố",
            Address: "65 Lý Tự Trọng",
          }],
          total: 1,
        };
      } else if (pathname === "/api/user/places/1") {
        payload = {
          place: {
            PlaceId: 1,
            PlaceName: "Bảo tàng Thành phố",
            Address: "65 Lý Tự Trọng",
          },
          category: { CategoryName: "Bảo tàng" },
          images: [{
            ImageId: "image-1",
            FileUrl: "/uploads/images/museum.jpg",
            Caption: "Mặt tiền bảo tàng",
          }],
          audios: [{
            AudioId: "audio-1",
            Title: "Câu chuyện của bảo tàng",
            Language: "Tiếng Việt",
            FileUrl: "/uploads/audio/story.mp3",
          }],
          narrations: [],
        };
      } else {
        throw new Error(`Unexpected request: ${pathname}`);
      }

      return {
        ok: true,
        status: 200,
        json: async () => payload,
      };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<UserDemo apiUrl="http://localhost:8000" />);

    expect(await screen.findByText("Bảo tàng Thành phố")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Đăng nhập để lưu" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Đăng nhập để lưu" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục khám phá" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/user/places?"),
      expect.objectContaining({ headers: expect.any(Headers) }),
    ));

    fireEvent.click(screen.getByRole("button", { name: "Xem chi tiết" }));
    expect(await screen.findByText("Câu chuyện của bảo tàng")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Mặt tiền bảo tàng" })).toHaveAttribute(
      "src",
      "http://localhost:8000/uploads/images/museum.jpg",
    );
    expect(screen.getByRole("button", { name: "Đăng nhập để lưu" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Đăng nhập để lưu" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục khám phá" }));

    fireEvent.ended(document.querySelector("audio"));

    expect(fetchMock.mock.calls.every(([, options]) => (
      !options.headers.has("Authorization")
    ))).toBe(true);
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/api/user/listening-history"),
      expect.anything(),
    );
  });

  it("uses localized place names and only shows audio for the selected audio language", async () => {
    const fetchMock = vi.fn(async (input) => {
      const { pathname } = new URL(String(input));
      const payload = pathname === "/api/user/categories"
        ? [{
          CategoryId: 3,
          CategoryName: "Bảo tàng",
          Translations: { en: { CategoryName: "Museum" } },
        }]
        : pathname === "/api/user/places"
          ? {
            items: [{
              PlaceId: 1,
              PlaceName: "Bảo tàng Thành phố",
              Translations: { en: { PlaceName: "City Museum" } },
              Address: "65 Lý Tự Trọng",
            }],
            total: 1,
          }
          : {
            place: {
              PlaceId: 1,
              PlaceName: "Bảo tàng Thành phố",
              Translations: { en: { PlaceName: "City Museum" } },
              Address: "65 Lý Tự Trọng",
            },
            category: {
              CategoryName: "Bảo tàng",
              Translations: { en: { CategoryName: "Museum" } },
            },
            images: [],
            audios: [{
              AudioId: "audio-vi",
              Title: "Vietnamese narration",
              Language: "vi",
              FileUrl: "/uploads/audio/story.mp3",
            }],
            narrations: [],
          };

      return {
        ok: true,
        status: 200,
        json: async () => payload,
      };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<UserDemo apiUrl="http://localhost:8000" locale="en" />);

    expect(await screen.findByText("City Museum")).toBeInTheDocument();
    expect(screen.getByLabelText("Categories")).toHaveTextContent("Museum");
    fireEvent.click(screen.getByRole("button", { name: "View details" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/user/places/1"),
      expect.objectContaining({ headers: expect.any(Headers) }),
    ));
    expect(await screen.findByRole("heading", { name: "City Museum" })).toBeInTheDocument();
    expect(await screen.findByText("No audio is available in the selected language."))
      .toBeInTheDocument();
    expect(document.querySelector("audio")).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Audio language" }), {
      target: { value: "vi" },
    });
    expect(document.querySelector("audio")).toBeInTheDocument();
  });
});
