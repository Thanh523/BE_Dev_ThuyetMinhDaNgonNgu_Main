import { useCallback, useEffect, useRef, useState } from "react";
import {
  getLocaleFormat,
  translateUserText,
  USER_LANGUAGES,
} from "../i18n/userTranslations.js";

const PLACE_PAGE_LIMIT = 12;
const SAVED_PLACES_PAGE_LIMIT = 10;
const LISTENING_HISTORY_PAGE_LIMIT = 10;

// Giữ mã HTTP để giao diện phân biệt lỗi dữ liệu với audio đã bị xóa/ngừng hoạt động.
class ApiRequestError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

// Tập trung xử lý header, response 204 và thông báo lỗi cho mọi API user.
async function userRequest(apiUrl, token, path, options = {}) {
  const headers = new Headers(options.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (options.body) {
    headers.set("Content-Type", "application/json");
  }

  let response;
  try {
    response = await fetch(`${apiUrl.replace(/\/+$/, "")}${path}`, {
      ...options,
      headers,
    });
  } catch (requestError) {
    if (requestError instanceof TypeError) {
      throw new Error(
        `Không kết nối được backend tại ${apiUrl}. Kiểm tra backend đang chạy và CORS cho địa chỉ trang demo.`,
      );
    }
    throw requestError;
  }
  if (response.status === 204) {
    return null;
  }

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    throw new ApiRequestError(
      typeof detail === "string"
        ? detail
        : `Yêu cầu thất bại (HTTP ${response.status}).`,
      response.status,
    );
  }
  return payload;
}

function formatDate(value, locale) {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleString(getLocaleFormat(locale));
}

function localizedField(item, locale, field) {
  return item?.Translations?.[locale]?.[field] || item?.[field] || "";
}

function audioLanguageCode(audio) {
  const language = USER_LANGUAGES.find((item) => (
    item.code === audio.Language
    || item.nativeName === audio.Language
    || item.name === audio.Language
  ));
  return language?.code || audio.Language;
}

export default function UserDemo({ apiUrl, locale = "vi", onTokenChange }) {
  const t = (text, values) => translateUserText(locale, text, values);
  const [authMode, setAuthMode] = useState("login");
  const [authForm, setAuthForm] = useState({
    full_name: "",
    email: "",
    password: "",
  });
  const [token, setToken] = useState("");
  const [profile, setProfile] = useState(null);
  const [profileForm, setProfileForm] = useState({ full_name: "" });
  const [editingProfile, setEditingProfile] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [accountPanel, setAccountPanel] = useState(null);
  const [loginPromptOpen, setLoginPromptOpen] = useState(false);
  const [passwordForm, setPasswordForm] = useState({
    current_password: "",
    new_password: "",
    confirm_password: "",
  });
  const [places, setPlaces] = useState([]);
  // Lưu danh mục và lựa chọn hiện tại để bộ lọc vẫn giữ nguyên khi chuyển trang.
  const [placeCategories, setPlaceCategories] = useState([]);
  const [categoriesLoading, setCategoriesLoading] = useState(false);
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [placeSearch, setPlaceSearch] = useState("");
  const [submittedPlaceSearch, setSubmittedPlaceSearch] = useState("");
  const [placesSkip, setPlacesSkip] = useState(0);
  const [placesTotal, setPlacesTotal] = useState(0);
  const [placesLoading, setPlacesLoading] = useState(false);
  const [placeDetails, setPlaceDetails] = useState(null);
  const [loadingPlaceDetailsId, setLoadingPlaceDetailsId] = useState(null);
  const [audiosByPlace, setAudiosByPlace] = useState({});
  const [audioLanguage, setAudioLanguage] = useState(locale);
  const [savedPlaces, setSavedPlaces] = useState([]);
  const [savedPlacesTotal, setSavedPlacesTotal] = useState(0);
  const [savedPlacesSkip, setSavedPlacesSkip] = useState(0);
  const [savedPlacesLoading, setSavedPlacesLoading] = useState(false);
  const [listeningHistory, setListeningHistory] = useState([]);
  const [listeningHistoryTotal, setListeningHistoryTotal] = useState(0);
  const [listeningHistorySkip, setListeningHistorySkip] = useState(0);
  const [listeningHistoryLoading, setListeningHistoryLoading] = useState(false);
  const [listeningHistoryRefresh, setListeningHistoryRefresh] = useState(0);
  const [replayingHistoryId, setReplayingHistoryId] = useState(null);
  const [deletingHistoryId, setDeletingHistoryId] = useState(null);
  const [clearingListeningHistory, setClearingListeningHistory] = useState(false);
  const [pendingReplayAudioId, setPendingReplayAudioId] = useState(null);
  const audioElements = useRef(new Map());
  const loginPromptRef = useRef(null);
  const sessionId = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    setAudioLanguage(locale);
  }, [locale]);

  useEffect(() => {
    onTokenChange?.(token);
  }, [onTokenChange, token]);

  useEffect(() => {
    if (loginPromptOpen) {
      loginPromptRef.current?.focus();
    }
  }, [loginPromptOpen]);

  // Tải dữ liệu cá nhân bằng token user; API tự giới hạn dữ liệu theo tài khoản.
  const refreshActivity = useCallback(async (activeToken) => {
    const currentProfile = await userRequest(apiUrl, activeToken, "/api/user/auth/me");
    setProfile(currentProfile);
    setProfileForm({ full_name: currentProfile.FullName });
  }, [apiUrl]);

  // Tạo phiên hoạt động và gửi heartbeat để Dashboard nhận diện tài khoản đang online.
  useEffect(() => {
    if (!token) {
      sessionId.current = null;
      return undefined;
    }

    let active = true;
    let heartbeat;
    userRequest(apiUrl, token, "/api/user/sessions", { method: "POST" })
      .then((session) => {
        if (!active) {
          return;
        }
        sessionId.current = session.SessionId;
        heartbeat = window.setInterval(() => {
          if (!sessionId.current) {
            return;
          }
          userRequest(
            apiUrl,
            token,
            `/api/user/sessions/${encodeURIComponent(sessionId.current)}`,
            {
              method: "PATCH",
              body: JSON.stringify({ end_session: false }),
            },
          ).catch(() => {
            // Dashboard sẽ tự loại phiên nếu heartbeat không còn được gửi.
          });
        }, 60 * 1000);
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError.message);
        }
      });

    return () => {
      active = false;
      if (heartbeat) {
        window.clearInterval(heartbeat);
      }
      const currentSessionId = sessionId.current;
      sessionId.current = null;
      if (currentSessionId) {
        userRequest(
          apiUrl,
          token,
          `/api/user/sessions/${encodeURIComponent(currentSessionId)}`,
          {
            method: "PATCH",
            body: JSON.stringify({ end_session: true }),
          },
        ).catch(() => {
          // Phiên hết hạn theo timeout nếu trình duyệt đã đóng hoặc mất mạng.
        });
      }
    };
  }, [apiUrl, token]);

  const loadListeningHistory = useCallback((activeToken, skip) => userRequest(
    apiUrl,
    activeToken,
    `/api/user/listening-history?skip=${skip}&limit=${LISTENING_HISTORY_PAGE_LIMIT}`,
  ), [apiUrl]);

  // Tải riêng trang lịch sử để danh sách dài không bị giới hạn ở 20 lượt đầu.
  useEffect(() => {
    if (!token) {
      setListeningHistory([]);
      setListeningHistoryTotal(0);
      setListeningHistorySkip(0);
      setDeletingHistoryId(null);
      setClearingListeningHistory(false);
      return undefined;
    }

    let active = true;
    setListeningHistoryLoading(true);
    loadListeningHistory(token, listeningHistorySkip)
      .then((history) => {
        if (active) {
          setListeningHistory(history.items);
          setListeningHistoryTotal(history.total);
        }
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError.message);
        }
      })
      .finally(() => {
        if (active) {
          setListeningHistoryLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [token, listeningHistorySkip, listeningHistoryRefresh, loadListeningHistory]);

  // Phát sau khi chi tiết địa điểm và phần tử audio đã được render.
  useEffect(() => {
    if (!pendingReplayAudioId) {
      return;
    }

    const audioElement = audioElements.current.get(String(pendingReplayAudioId));
    if (!audioElement) {
      return;
    }

    setPendingReplayAudioId(null);
    audioElement.scrollIntoView({ behavior: "smooth", block: "center" });
    audioElement.play().catch(() => {
      setError("Trình duyệt không phát được audio. Hãy thử nhấn nút phát trên audio.");
    });
  }, [pendingReplayAudioId, placeDetails, audiosByPlace]);

  const loadSavedPlaces = useCallback(async (activeToken, skip = savedPlacesSkip) => {
    return userRequest(
      apiUrl,
      activeToken,
      `/api/user/saved-places?skip=${skip}&limit=${SAVED_PLACES_PAGE_LIMIT}`,
    );
  }, [apiUrl, savedPlacesSkip]);

  // Tải trang bookmark đang chọn; bỏ kết quả cũ nếu user đổi trang giữa lúc chờ API.
  useEffect(() => {
    if (!token) {
      setSavedPlaces([]);
      setSavedPlacesTotal(0);
      setSavedPlacesSkip(0);
      return undefined;
    }

    let active = true;
    setSavedPlacesLoading(true);
    loadSavedPlaces(token, savedPlacesSkip)
      .then((saved) => {
        if (active) {
          setSavedPlaces(saved.items);
          setSavedPlacesTotal(saved.total);
        }
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError.message);
        }
      })
      .finally(() => {
        if (active) {
          setSavedPlacesLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [token, savedPlacesSkip, loadSavedPlaces]);

  // Chỉ tìm khi submit; cờ active bỏ qua kết quả cũ nếu user đổi trang hoặc bộ lọc.
  // Gửi category_id cùng truy vấn để backend lọc trước khi phân trang.
  useEffect(() => {
    let active = true;
    const params = new URLSearchParams({
      search: submittedPlaceSearch,
      skip: String(placesSkip),
      limit: String(PLACE_PAGE_LIMIT),
    });
    if (selectedCategoryId) {
      params.set("category_id", selectedCategoryId);
    }
    setPlacesLoading(true);
    userRequest(apiUrl, token, `/api/user/places?${params.toString()}`)
      .then((result) => {
        if (active) {
          setPlaces(result.items);
          setPlacesTotal(result.total);
        }
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError.message);
        }
      })
      .finally(() => {
        if (active) {
          setPlacesLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [apiUrl, token, submittedPlaceSearch, selectedCategoryId, placesSkip]);

  // Đăng ký không tự đăng nhập; sau khi tạo tài khoản, người dùng đăng nhập riêng.
  async function submitAuth(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (authMode === "register") {
        await userRequest(apiUrl, "", "/api/user/auth/register", {
          method: "POST",
          body: JSON.stringify(authForm),
        });
        setAuthMode("login");
        setAuthForm((current) => ({ ...current, password: "" }));
        setNotice("Đăng ký thành công. Hãy đăng nhập bằng tài khoản vừa tạo.");
      } else {
        const result = await userRequest(apiUrl, "", "/api/user/auth/login", {
          method: "POST",
          body: JSON.stringify({
            email: authForm.email,
            password: authForm.password,
          }),
        });
        setToken(result.access_token);
        setAuthForm((current) => ({ ...current, password: "" }));
        setNotice("Đăng nhập user thành công.");
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    setToken("");
    setProfile(null);
    setProfileForm({ full_name: "" });
    setEditingProfile(false);
    setChangingPassword(false);
    setPasswordForm({
      current_password: "",
      new_password: "",
      confirm_password: "",
    });
    setSavedPlaces([]);
    setSavedPlacesTotal(0);
    setSavedPlacesSkip(0);
    setListeningHistory([]);
    setListeningHistoryTotal(0);
    setListeningHistorySkip(0);
    setDeletingHistoryId(null);
    setClearingListeningHistory(false);
    setPlaces([]);
    setPlaceCategories([]);
    setSelectedCategoryId("");
    setPlacesTotal(0);
    setPlacesSkip(0);
    setPlaceDetails(null);
    setLoadingPlaceDetailsId(null);
    setAudiosByPlace({});
    setNotice("Đã đăng xuất user.");
    setError("");
  }

  // Tạo một request action dùng chung để thống nhất trạng thái tải và thông báo.
  async function runAction(action, successMessage, afterSuccess) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      if (afterSuccess) {
        await afterSuccess();
      }
      setNotice(successMessage);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  function requireLogin() {
    setLoginPromptOpen(true);
  }

  function goToLogin() {
    setLoginPromptOpen(false);
    window.setTimeout(() => {
      const authPanel = document.querySelector(".user-auth-panel");
      authPanel?.scrollIntoView({ behavior: "smooth", block: "center" });
      authPanel?.querySelector('input[type="email"]')?.focus();
    }, 0);
  }

  async function toggleSavedPlace(place) {
    const isSaved = savedPlaces.some(
      (item) => Number(item.PlaceId) === Number(place.PlaceId),
    );
    await runAction(
      () => userRequest(
        apiUrl,
        token,
        `/api/user/saved-places/${place.PlaceId}`,
        { method: isSaved ? "DELETE" : "POST" },
      ),
      isSaved ? "Đã bỏ lưu địa điểm." : "Đã lưu địa điểm.",
      async () => {
        await refreshActivity(token);
        let nextSkip = savedPlacesSkip;
        let saved = await loadSavedPlaces(token, nextSkip);
        if (
          isSaved
          && saved.items.length === 0
          && nextSkip > 0
        ) {
          nextSkip = Math.max(0, nextSkip - SAVED_PLACES_PAGE_LIMIT);
          setSavedPlacesSkip(nextSkip);
          saved = await loadSavedPlaces(token, nextSkip);
        }
        setSavedPlaces(saved.items);
        setSavedPlacesTotal(saved.total);
      },
    );
  }

  async function saveProfile(event) {
    event.preventDefault();
    await runAction(
      () => userRequest(apiUrl, token, "/api/user/auth/me", {
        method: "PATCH",
        body: JSON.stringify({ full_name: profileForm.full_name }),
      }),
      "Đã cập nhật hồ sơ.",
      async () => {
        setEditingProfile(false);
        await refreshActivity(token);
      },
    );
  }

  async function changePassword(event) {
    event.preventDefault();
    // So khớp ngay trên giao diện để tránh gửi mật khẩu mới không khớp lên server.
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setError("Mật khẩu mới nhập lại không khớp.");
      setNotice("");
      return;
    }

    await runAction(
      () => userRequest(apiUrl, token, "/api/user/auth/me/password", {
        method: "PATCH",
        body: JSON.stringify({
          current_password: passwordForm.current_password,
          new_password: passwordForm.new_password,
        }),
      }),
      "Đã đổi mật khẩu thành công.",
      () => {
        setPasswordForm({
          current_password: "",
          new_password: "",
          confirm_password: "",
        });
        setChangingPassword(false);
      },
    );
  }

  async function openPlaceDetails(place) {
    setLoadingPlaceDetailsId(place.PlaceId);
    setError("");
    setNotice("");
    try {
      // Lấy một bộ dữ liệu chi tiết đã lọc visible từ API user, không gọi API admin.
      const details = await userRequest(
        apiUrl,
        token,
        `/api/user/places/${place.PlaceId}`,
      );
      setPlaceDetails(details);
      setAudiosByPlace((current) => ({
        ...current,
        [place.PlaceId]: details.audios,
      }));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoadingPlaceDetailsId(null);
    }
  }

  async function replayHistoryItem(item) {
    const placeId = Number(item.PlaceId);
    if (!item.AudioId || !Number.isInteger(placeId) || placeId <= 0) {
      setError("Lượt nghe này không còn đủ thông tin để phát lại.");
      return;
    }

    setReplayingHistoryId(item.ListeningHistoryId);
    setError("");
    setNotice("");
    try {
      const details = await userRequest(
        apiUrl,
        token,
        `/api/user/places/${placeId}`,
      );
      const audio = details.audios.find(
        (candidate) => String(candidate.AudioId) === String(item.AudioId),
      );
      if (!audio) {
        setError("Audio này đã bị xóa hoặc ngừng hoạt động nên không thể nghe lại.");
        return;
      }

      setPlaceDetails(details);
      setAudiosByPlace((current) => ({
        ...current,
        [details.place.PlaceId]: details.audios,
      }));
      setPendingReplayAudioId(audio.AudioId);
      setNotice(t("Đang phát lại “{title}”.", { title: audio.Title }));
    } catch (requestError) {
      setError(
        requestError.status === 404
          ? "Địa điểm hoặc audio không còn khả dụng để phát lại."
          : requestError.message,
      );
    } finally {
      setReplayingHistoryId(null);
    }
  }

  async function deleteListeningHistoryEntry(item) {
    if (!window.confirm(t("Xóa lượt nghe này khỏi lịch sử?"))) {
      return;
    }

    setDeletingHistoryId(item.ListeningHistoryId);
    setError("");
    setNotice("");
    try {
      await userRequest(
        apiUrl,
        token,
        `/api/user/listening-history/${encodeURIComponent(item.ListeningHistoryId)}`,
        { method: "DELETE" },
      );
      setListeningHistory((current) => current.filter(
        (entry) => entry.ListeningHistoryId !== item.ListeningHistoryId,
      ));
      setListeningHistoryTotal((current) => Math.max(0, current - 1));
      setNotice("Đã xóa lượt nghe khỏi lịch sử.");

      if (listeningHistory.length === 1 && listeningHistorySkip > 0) {
        setListeningHistorySkip((current) => (
          Math.max(0, current - LISTENING_HISTORY_PAGE_LIMIT)
        ));
      } else {
        setListeningHistoryRefresh((current) => current + 1);
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setDeletingHistoryId(null);
    }
  }

  async function clearListeningHistory() {
    if (!window.confirm(t("Xóa toàn bộ lịch sử nghe? Thao tác này không thể hoàn tác."))) {
      return;
    }

    setClearingListeningHistory(true);
    setError("");
    setNotice("");
    try {
      await userRequest(
        apiUrl,
        token,
        "/api/user/listening-history",
        { method: "DELETE" },
      );
      setListeningHistory([]);
      setListeningHistoryTotal(0);
      setListeningHistorySkip(0);
      setNotice("Đã xóa toàn bộ lịch sử nghe.");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setClearingListeningHistory(false);
    }
  }

  async function recordAudioPlayback(audio, element, completed) {
    const playedSeconds = Math.floor(
      completed ? element.duration : element.currentTime,
    );
    if (!Number.isFinite(playedSeconds) || playedSeconds <= 0) {
      return;
    }

    // Tạm dừng lưu tiến độ; sự kiện ended lưu cùng thời lượng và đánh dấu hoàn tất.
    try {
      await userRequest(
        apiUrl,
        token,
        token
          ? "/api/user/listening-history"
          : "/api/user/listening-usage",
        {
          method: "POST",
          body: JSON.stringify({
            audio_id: audio.AudioId,
            played_seconds: playedSeconds,
            is_completed: completed,
          }),
        },
      );
      if (token) {
        await refreshActivity(token);
        setListeningHistorySkip(0);
        setListeningHistoryRefresh((current) => current + 1);
        setNotice(
          completed
            ? t("Đã nghe xong “{title}”, lịch sử đã được lưu.", {
              title: audio.Title,
            })
            : t("Đã lưu tiến độ nghe “{title}”.", { title: audio.Title }),
        );
      }
      setError("");
    } catch (requestError) {
      if (requestError.status === 404) {
        try {
          const currentAudios = await userRequest(
            apiUrl,
            token,
            `/api/user/places/${audio.PlaceId}/audios`,
          );
          setAudiosByPlace((current) => ({
            ...current,
            [audio.PlaceId]: currentAudios,
          }));
          setError(
            t("Audio “{title}” không còn hoạt động; danh sách audio đã được làm mới.", {
              title: audio.Title,
            }),
          );
        } catch (refreshError) {
          setError(refreshError.message);
        }
      } else {
        setError(requestError.message);
      }
    }
  }

  async function removePlace(id) {
    await runAction(
      () => userRequest(
        apiUrl,
        token,
        `/api/user/saved-places/${encodeURIComponent(id)}`,
        { method: "DELETE" },
      ),
      "Đã bỏ lưu địa điểm.",
      async () => {
        await refreshActivity(token);
        const nextSkip = (
          savedPlaces.length === 1 && savedPlacesSkip > 0
            ? Math.max(0, savedPlacesSkip - SAVED_PLACES_PAGE_LIMIT)
            : savedPlacesSkip
        );
        if (nextSkip !== savedPlacesSkip) {
          setSavedPlacesSkip(nextSkip);
        }
        const saved = await loadSavedPlaces(token, nextSkip);
        setSavedPlaces(saved.items);
        setSavedPlacesTotal(saved.total);
      },
    );
  }

  // Danh mục và địa điểm visible được phép xem ở chế độ khách.
  useEffect(() => {
    let active = true;
    setCategoriesLoading(true);
    userRequest(apiUrl, "", "/api/user/categories")
      .then((categories) => {
        if (active) {
          setPlaceCategories(categories);
        }
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError.message);
        }
      })
      .finally(() => {
        if (active) {
          setCategoriesLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [apiUrl]);

  // Nếu admin khóa user ở nơi khác, yêu cầu API kế tiếp sẽ thu hồi phiên demo này.
  useEffect(() => {
    if (!token) {
      return;
    }
    let active = true;
    refreshActivity(token)
      .catch((requestError) => {
        if (active) {
          setError(requestError.message);
          setToken("");
        }
      });
    return () => {
      active = false;
    };
  }, [apiUrl, token, refreshActivity]);

  return (
    <section className="user-demo">
      {!token ? (
        <section className="panel user-auth-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">{t("CHẾ ĐỘ KHÁCH")}</p>
              <h2>
                {authMode === "login"
                  ? t("Bạn đang khám phá với tư cách khách")
                  : t("Tạo tài khoản user")}
              </h2>
            </div>
            <span className="status-pill">{t("Không cần đăng nhập")}</span>
          </div>
          {authMode === "login" && (
            <p className="guest-access-note">
              {t("Bạn có thể xem địa điểm, đọc thuyết minh và nghe audio ngay bây giờ. Đăng nhập khi muốn lưu địa điểm hoặc xem lịch sử nghe.")}
            </p>
          )}
          <form className="user-demo-form" onSubmit={submitAuth}>
            {authMode === "register" && (
              <label>
                {t("Họ tên")}
                <input
                  autoComplete="name"
                  maxLength={200}
                  onChange={(event) => setAuthForm((current) => ({
                    ...current,
                    full_name: event.target.value,
                  }))}
                  required
                  value={authForm.full_name}
                />
              </label>
            )}
            <label>
              {t("Email")}
              <input
                autoComplete="email"
                maxLength={254}
                onChange={(event) => setAuthForm((current) => ({
                  ...current,
                  email: event.target.value,
                }))}
                required
                type="email"
                value={authForm.email}
              />
            </label>
            <label>
              {t("Mật khẩu")} {authMode === "register" && t("(12-128 ký tự)")}
              <input
                autoComplete={authMode === "register" ? "new-password" : "current-password"}
                maxLength={128}
                minLength={authMode === "register" ? 12 : 1}
                onChange={(event) => setAuthForm((current) => ({
                  ...current,
                  password: event.target.value,
                }))}
                required
                type="password"
                value={authForm.password}
              />
            </label>
            <div className="user-demo-actions">
              <button className="button" disabled={busy} type="submit">
                {busy
                  ? t("Đang xử lý...")
                  : authMode === "login"
                    ? t("Đăng nhập")
                    : t("Đăng ký")}
              </button>
              <button
                className="button button-outline"
                disabled={busy}
                onClick={() => {
                  setAuthMode((current) => (
                    current === "login" ? "register" : "login"
                  ));
                  setError("");
                  setNotice("");
                }}
                type="button"
              >
                {authMode === "login"
                  ? t("Chưa có tài khoản? Đăng ký")
                  : t("Đã có tài khoản? Đăng nhập")}
              </button>
            </div>
          </form>
          <p className="hint">
            {t("Demo gọi API backend; JWT user chỉ lưu trong bộ nhớ trang và không được dùng để truy cập chức năng admin.")}
          </p>
        </section>
      ) : (
        <>
          <div className="user-account-bar">
            <div className="user-account-welcome">
              <span className="user-account-kicker">{t("KHÔNG GIAN CỦA BẠN")}</span>
              <strong>{t("Xin chào, {name}!", { name: profile?.FullName || t("bạn") })}</strong>
            </div>
            <div className="user-account-menu-wrap">
              <button
                aria-expanded={accountMenuOpen}
                aria-haspopup="menu"
                className="user-avatar-button"
                onClick={() => setAccountMenuOpen((current) => !current)}
                type="button"
              >
                <span className="user-avatar" aria-hidden="true">
                  {(profile?.FullName || profile?.Email || "?").slice(0, 1).toUpperCase()}
                </span>
                <span className="user-avatar-label">{t("Tài khoản")}</span>
                <span aria-hidden="true">⌄</span>
              </button>
              {accountMenuOpen && (
                <div className="user-account-menu" role="menu">
                  <button
                    onClick={() => {
                      setAccountPanel("profile");
                      setAccountMenuOpen(false);
                      setError("");
                      setNotice("");
                    }}
                    role="menuitem"
                    type="button"
                  >
                    <span aria-hidden="true">◯</span>
                    {t("Sửa hồ sơ & bảo mật")}
                  </button>
                  <button
                    onClick={() => {
                      setAccountPanel("saved");
                      setAccountMenuOpen(false);
                    }}
                    role="menuitem"
                    type="button"
                  >
                    <span aria-hidden="true">♡</span>
                    {t("Địa điểm đã lưu")}
                  </button>
                  <button
                    onClick={() => {
                      setAccountPanel("history");
                      setAccountMenuOpen(false);
                    }}
                    role="menuitem"
                    type="button"
                  >
                    <span aria-hidden="true">◷</span>
                    {t("Lịch sử nghe")}
                  </button>
                  <div className="user-account-menu-divider" />
                  <button
                    className="user-account-menu-logout"
                    onClick={logout}
                    role="menuitem"
                    type="button"
                  >
                    <span aria-hidden="true">↪</span>
                    {t("Đăng xuất")}
                  </button>
                </div>
              )}
            </div>
          </div>

          {accountPanel === "profile" && (
            <>
          <section className="panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">{t("TÀI KHOẢN CỦA TÔI")}</p>
                <h2>{editingProfile ? t("Chỉnh sửa hồ sơ") : t("Hồ sơ người dùng")}</h2>
              </div>
              <div className="user-demo-actions">
                <span className="status-pill status-connected">{t("Đã đăng nhập")}</span>
              </div>
            </div>
            {editingProfile ? (
              <form className="user-demo-profile-form" onSubmit={saveProfile}>
                <div className="user-profile-fields">
                  <label>
                    {t("Họ tên")}
                    <input
                      autoComplete="name"
                      maxLength={200}
                      minLength={1}
                      onChange={(event) => setProfileForm((current) => ({
                        ...current,
                        full_name: event.target.value,
                      }))}
                      required
                      value={profileForm.full_name}
                    />
                  </label>
                  <label>
                    {t("Email")}
                    <input
                      readOnly
                      value={profile?.Email ?? ""}
                    />
                  </label>
                </div>
                <p className="hint">
                  {t("Email chưa thể thay đổi vì tài khoản hiện chưa có bước xác minh email.")}
                </p>
                <div className="user-profile-actions">
                  <button className="button" disabled={busy} type="submit">
                    {busy ? t("Đang lưu...") : t("Lưu thay đổi")}
                  </button>
                  <button
                    className="button button-outline"
                    disabled={busy}
                    onClick={() => {
                      setProfileForm({ full_name: profile?.FullName ?? "" });
                      setEditingProfile(false);
                      setError("");
                    }}
                    type="button"
                  >
                    {t("Hủy")}
                  </button>
                </div>
              </form>
            ) : (
              <dl className="user-profile-details">
                <div>
                  <dt>{t("Họ tên")}</dt>
                  <dd>{profile?.FullName ?? "—"}</dd>
                </div>
                <div>
                  <dt>{t("Email")}</dt>
                  <dd>{profile?.Email ?? "—"}</dd>
                </div>
                <div>
                  <dt>{t("Ngày tạo tài khoản")}</dt>
                  <dd>{formatDate(profile?.CreatedAt, locale)}</dd>
                </div>
                <div>
                  <dt>{t("Đăng nhập gần nhất")}</dt>
                  <dd>{formatDate(profile?.LastLoginAt, locale)}</dd>
                </div>
              </dl>
            )}
          </section>

          <section className="panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">{t("BẢO MẬT TÀI KHOẢN")}</p>
                <h2>{t("Đổi mật khẩu")}</h2>
              </div>
              {!changingPassword && (
                <button
                  className="button button-outline"
                  onClick={() => {
                    setChangingPassword(true);
                    setError("");
                    setNotice("");
                  }}
                  type="button"
                >
                  {t("Đổi mật khẩu")}
                </button>
              )}
            </div>
            {changingPassword && (
              <form className="user-demo-profile-form" onSubmit={changePassword}>
                <div className="user-password-fields">
                  <label>
                    {t("Mật khẩu hiện tại")}
                    <input
                      autoComplete="current-password"
                      maxLength={128}
                      onChange={(event) => setPasswordForm((current) => ({
                        ...current,
                        current_password: event.target.value,
                      }))}
                      required
                      type="password"
                      value={passwordForm.current_password}
                    />
                  </label>
                  <label>
                    {t("Mật khẩu mới")}
                    <input
                      autoComplete="new-password"
                      maxLength={128}
                      minLength={12}
                      onChange={(event) => setPasswordForm((current) => ({
                        ...current,
                        new_password: event.target.value,
                      }))}
                      required
                      type="password"
                      value={passwordForm.new_password}
                    />
                  </label>
                  <label>
                    {t("Nhập lại mật khẩu mới")}
                    <input
                      autoComplete="new-password"
                      maxLength={128}
                      minLength={12}
                      onChange={(event) => setPasswordForm((current) => ({
                        ...current,
                        confirm_password: event.target.value,
                      }))}
                      required
                      type="password"
                      value={passwordForm.confirm_password}
                    />
                  </label>
                </div>
                <p className="hint">{t("Mật khẩu mới cần có ít nhất 12 ký tự.")}</p>
                <div className="user-profile-actions">
                  <button className="button" disabled={busy} type="submit">
                    {busy ? t("Đang cập nhật...") : t("Cập nhật mật khẩu")}
                  </button>
                  <button
                    className="button button-outline"
                    disabled={busy}
                    onClick={() => {
                      setChangingPassword(false);
                      setPasswordForm({
                        current_password: "",
                        new_password: "",
                        confirm_password: "",
                      });
                      setError("");
                    }}
                    type="button"
                  >
                    {t("Hủy")}
                  </button>
                </div>
              </form>
            )}
          </section>
          </>
          )}

          </>
        )}

          <section className="panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">EXPLORE PLACES</p>
                <h2>{t("Khám phá địa điểm")}</h2>
              </div>
              <span className="muted-count">{t("địa điểm", { count: placesTotal })}</span>
            </div>
            <form
              className="place-filters user-place-search"
              onSubmit={(event) => {
                event.preventDefault();
                setPlacesSkip(0);
                setSubmittedPlaceSearch(placeSearch.trim());
              }}
            >
              <label>
                {t("Tìm địa điểm")}
                <input
                  onChange={(event) => setPlaceSearch(event.target.value)}
                  placeholder={t("Tìm theo tên, địa chỉ, danh mục...")}
                  value={placeSearch}
                />
              </label>
              <label>
                {t("Danh mục")}
                <select
                  disabled={categoriesLoading}
                  onChange={(event) => {
                    // Đổi danh mục cần quay về trang đầu và đóng chi tiết cũ nếu đang mở.
                    setPlacesSkip(0);
                    setSelectedCategoryId(event.target.value);
                    setPlaceDetails(null);
                  }}
                  value={selectedCategoryId}
                >
                  <option value="">
                    {categoriesLoading
                      ? t("Đang tải danh mục...")
                      : t("Tất cả danh mục")}
                  </option>
                  {placeCategories.map((category) => (
                    <option key={category.CategoryId} value={category.CategoryId}>
                      {localizedField(category, locale, "CategoryName")}
                    </option>
                  ))}
                </select>
              </label>
              <button className="button" disabled={placesLoading} type="submit">
                {t("Tìm kiếm")}
              </button>
            </form>
            {placeDetails ? (
              <article className="user-place-detail">
                {/* Khi đã chọn địa điểm, thay danh sách bằng thông tin đầy đủ và nút quay lại. */}
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">
                      {localizedField(placeDetails.category, locale, "CategoryName")
                        || t("ĐỊA ĐIỂM")}
                    </p>
                    <h2>{localizedField(placeDetails.place, locale, "PlaceName")}</h2>
                    <p className="subtitle">{placeDetails.place.Address}</p>
                  </div>
                  <button
                    className="button button-outline"
                    onClick={() => setPlaceDetails(null)}
                    type="button"
                  >
                    {t("Quay lại danh sách")}
                  </button>
                </div>
                {placeDetails.category?.Description && (
                  <p className="user-place-category-description">
                    {localizedField(placeDetails.category, locale, "Description")}
                  </p>
                )}
                {placeDetails.place.Description && (
                  <p className="user-place-description">
                    {placeDetails.place.Description}
                  </p>
                )}
                {(placeDetails.images ?? []).length > 0 && (
                  <section
                    aria-label={t("Ảnh {name}", {
                      name: localizedField(placeDetails.place, locale, "PlaceName"),
                    })}
                    className="user-place-image-grid"
                  >
                    {placeDetails.images.map((image) => (
                      <figure key={image.ImageId}>
                        <img
                          alt={image.Caption
                            || localizedField(placeDetails.place, locale, "PlaceName")}
                          src={new URL(
                            image.FileUrl,
                            `${apiUrl.replace(/\/+$/, "")}/`,
                          ).toString()}
                        />
                        {image.Caption && <figcaption>{image.Caption}</figcaption>}
                      </figure>
                    ))}
                  </section>
                )}
                <div className="user-place-narrations">
                  <h3>{t("Nội dung thuyết minh")}</h3>
                  {(placeDetails.narrations ?? [])
                    .filter((narration) => narration.LanguageCode === locale)
                    .map((narration) => (
                    <article className="user-place-narration" key={narration.NarrationId}>
                      <div className="user-place-narration-heading">
                        <strong>{narration.Title}</strong>
                        <span>{USER_LANGUAGES.find((item) => item.code === narration.LanguageCode)?.nativeName
                          || narration.LanguageCode}</span>
                      </div>
                      <p>{narration.Content}</p>
                    </article>
                  ))}
                    {(placeDetails.narrations ?? [])
                      .filter((narration) => narration.LanguageCode === locale).length === 0 && (
                      <p>{t("Không có nội dung thuyết minh bằng ngôn ngữ đã chọn.")}</p>
                    )}
                </div>
                <div className="user-place-detail-actions">
                  <button
                    aria-pressed={savedPlaces.some(
                      (item) => Number(item.PlaceId)
                        === Number(placeDetails.place.PlaceId),
                    )}
                    className={`button ${
                      savedPlaces.some(
                        (item) => Number(item.PlaceId)
                          === Number(placeDetails.place.PlaceId),
                      )
                        ? "button-outline"
                        : ""
                    }`}
                    disabled={busy}
                    onClick={() => (
                      token
                        ? toggleSavedPlace(placeDetails.place)
                        : requireLogin()
                    )}
                    type="button"
                  >
                    {!token
                      ? t("Đăng nhập để lưu")
                      : savedPlaces.some(
                        (item) => Number(item.PlaceId)
                          === Number(placeDetails.place.PlaceId),
                      )
                        ? t("Đã lưu · Bỏ lưu")
                        : t("Lưu địa điểm")}
                  </button>
                </div>
                <div className="user-place-detail-audios">
                  <h3>{t("Thuyết minh audio")}</h3>
                  <label className="user-audio-language">
                    {t("Chọn ngôn ngữ audio")}
                    <select
                      onChange={(event) => setAudioLanguage(event.target.value)}
                      value={audioLanguage}
                    >
                      {USER_LANGUAGES.map((language) => (
                        <option key={language.code} value={language.code}>
                          {language.nativeName}
                        </option>
                      ))}
                    </select>
                  </label>
                  {(audiosByPlace[placeDetails.place.PlaceId] ?? [])
                    .filter((audio) => audioLanguageCode(audio) === audioLanguage).length === 0 ? (
                    <p>
                      {(audiosByPlace[placeDetails.place.PlaceId] ?? []).length === 0
                        ? t("Địa điểm này chưa có audio thuyết minh.")
                        : t("Không có audio bằng ngôn ngữ đã chọn.")}
                    </p>
                  ) : (
                    audiosByPlace[placeDetails.place.PlaceId]
                      .filter((audio) => audioLanguageCode(audio) === audioLanguage)
                      .map((audio) => (
                      <div className="user-place-audio" key={audio.AudioId}>
                        <div>
                          <strong>{audio.Title}</strong>
                          <span>
                            {USER_LANGUAGES.find((item) => item.code === audio.Language)?.nativeName
                              || audio.Language}
                            {audio.DurationSeconds
                              ? t(" · {seconds} giây", {
                                seconds: audio.DurationSeconds,
                              })
                              : ""}
                          </span>
                        </div>
                        <audio
                          controls
                          onEnded={(event) => recordAudioPlayback(
                            audio,
                            event.currentTarget,
                            true,
                          )}
                          onPause={(event) => {
                            if (!event.currentTarget.ended) {
                              recordAudioPlayback(
                                audio,
                                event.currentTarget,
                                false,
                              );
                            }
                          }}
                          onError={() => setError(t("Không phát được audio “{title}”.", {
                            title: audio.Title,
                          }))}
                          preload="none"
                          ref={(element) => {
                            if (element) {
                              audioElements.current.set(String(audio.AudioId), element);
                            } else {
                              audioElements.current.delete(String(audio.AudioId));
                            }
                          }}
                          src={new URL(
                            audio.FileUrl,
                            `${apiUrl.replace(/\/+$/, "")}/`,
                          ).toString()}
                        />
                      </div>
                    ))
                  )}
                </div>
              </article>
            ) : placesLoading ? (
              <p className="user-place-empty">{t("Đang tải địa điểm...")}</p>
            ) : places.length === 0 ? (
              <p className="user-place-empty">{t("Không tìm thấy địa điểm phù hợp.")}</p>
            ) : (
              <div className="user-place-grid">
                {places.map((place) => {
                  const isSaved = savedPlaces.some(
                    (item) => Number(item.PlaceId) === Number(place.PlaceId),
                  );
                  return (
                    <article className="user-place-card" key={place.PlaceId}>
                      <div>
                        <p className="eyebrow">{t("ĐỊA ĐIỂM")} #{place.PlaceId}</p>
                        <h3>{localizedField(place, locale, "PlaceName")}</h3>
                        <p>{place.Address}</p>
                      </div>
                      <div className="user-place-actions">
                        <button
                          aria-pressed={isSaved}
                          className={`button ${isSaved ? "button-outline" : ""}`}
                          disabled={busy}
                          onClick={() => (token ? toggleSavedPlace(place) : requireLogin())}
                          type="button"
                        >
                          {!token
                            ? t("Đăng nhập để lưu")
                            : isSaved
                              ? t("Đã lưu · Bỏ lưu")
                              : t("Lưu địa điểm")}
                        </button>
                        <button
                          className="text-button"
                          disabled={loadingPlaceDetailsId === place.PlaceId}
                          onClick={() => openPlaceDetails(place)}
                          type="button"
                        >
                          {loadingPlaceDetailsId === place.PlaceId
                            ? t("Đang tải chi tiết...")
                            : t("Xem chi tiết")}
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
            {!placeDetails && placesTotal > PLACE_PAGE_LIMIT && (
              <div className="user-place-pagination">
                <button
                  className="button button-outline"
                  disabled={placesLoading || placesSkip === 0}
                  onClick={() => setPlacesSkip((current) => (
                    Math.max(0, current - PLACE_PAGE_LIMIT)
                  ))}
                  type="button"
                >
                  {t("Trang trước")}
                </button>
                <span>
                  Trang {Math.floor(placesSkip / PLACE_PAGE_LIMIT) + 1} /{" "}
                  {Math.ceil(placesTotal / PLACE_PAGE_LIMIT)}
                </span>
                <button
                  className="button button-outline"
                  disabled={
                    placesLoading
                    || placesSkip + PLACE_PAGE_LIMIT >= placesTotal
                  }
                  onClick={() => setPlacesSkip((current) => (
                    current + PLACE_PAGE_LIMIT
                  ))}
                  type="button"
                >
                  {t("Trang sau")}
                </button>
              </div>
            )}
          </section>

          {token && (accountPanel === "saved" || accountPanel === "history") && (
          <section className="user-demo-grid user-account-content">
            <section className="panel">
              {accountPanel === "saved" ? (
              <div>
              <div className="section-heading">
                <div>
                  <p className="eyebrow">SAVED PLACES</p>
                  <h2>{t("Địa điểm đã lưu")}</h2>
                </div>
                <span className="muted-count">{t("địa điểm", { count: savedPlacesTotal })}</span>
              </div>
              <ul className="user-demo-list">
                {savedPlaces.map((item) => (
                  <li key={item.SavedPlaceId}>
                    <span>
                      {localizedField(item, locale, "PlaceName")
                        || t("Địa điểm không còn tồn tại")}
                      <small>{t("Lưu lúc {date}", {
                        date: formatDate(item.SavedAt, locale),
                      })}</small>
                    </span>
                    <button
                      className="text-button danger-text"
                      disabled={busy}
                      onClick={() => removePlace(item.PlaceId)}
                      type="button"
                    >
                      {t("Bỏ lưu")}
                    </button>
                  </li>
                ))}
                {savedPlacesLoading ? (
                  <li className="muted-row">{t("Đang tải địa điểm đã lưu...")}</li>
                ) : savedPlaces.length === 0 ? (
                  <li className="muted-row">{t("Chưa có địa điểm nào được lưu.")}</li>
                ) : null}
              </ul>
              {savedPlacesTotal > SAVED_PLACES_PAGE_LIMIT && (
                <div className="user-place-pagination">
                  <button
                    className="button button-outline"
                    disabled={savedPlacesLoading || savedPlacesSkip === 0}
                    onClick={() => setSavedPlacesSkip((current) => (
                      Math.max(0, current - SAVED_PLACES_PAGE_LIMIT)
                    ))}
                    type="button"
                  >
                    {t("Trang trước")}
                  </button>
                  <span>
                    Trang {Math.floor(savedPlacesSkip / SAVED_PLACES_PAGE_LIMIT) + 1} /{" "}
                    {Math.ceil(savedPlacesTotal / SAVED_PLACES_PAGE_LIMIT)}
                  </span>
                  <button
                    className="button button-outline"
                    disabled={
                      savedPlacesLoading
                      || savedPlacesSkip + SAVED_PLACES_PAGE_LIMIT >= savedPlacesTotal
                    }
                    onClick={() => setSavedPlacesSkip((current) => (
                      current + SAVED_PLACES_PAGE_LIMIT
                    ))}
                    type="button"
                  >
                    {t("Trang sau")}
                  </button>
                </div>
              )}
              </div>
              ) : (
              <div>
              <div className="section-heading">
                <div>
                  <p className="eyebrow">LISTENING HISTORY</p>
                  <h2>{t("Lịch sử nghe")}</h2>
                </div>
                <div className="user-history-actions">
                  <span className="muted-count">{t("lượt nghe", {
                    count: listeningHistoryTotal,
                  })}</span>
                  <button
                    className="text-button danger-text"
                    disabled={
                      listeningHistoryTotal === 0
                      || listeningHistoryLoading
                      || clearingListeningHistory
                      || deletingHistoryId !== null
                    }
                    onClick={clearListeningHistory}
                    type="button"
                  >
                    {clearingListeningHistory ? t("Đang xóa...") : t("Xóa tất cả")}
                  </button>
                </div>
              </div>
              <ul className="user-demo-list">
                {listeningHistory.map((item) => (
                  <li key={item.ListeningHistoryId}>
                    <span>
                      <strong>
                        {item.AudioTitle ?? t("Audio {id} không còn tồn tại", {
                          id: item.AudioId ?? "",
                        })}
                      </strong>
                      <small>
                        {localizedField(item, locale, "PlaceName")
                          || t("Địa điểm không còn tồn tại")}
                        {item.Language
                          ? ` · ${USER_LANGUAGES.find((language) => language.code === item.Language)?.nativeName
                            || item.Language}`
                          : ""}
                      </small>
                      <small>
                        {t("Đã nghe {seconds}s · {status}", {
                          seconds: item.PlayedSeconds,
                          status: item.IsCompleted
                            ? t("Hoàn thành")
                            : t("Chưa hoàn thành"),
                        })} · {formatDate(item.ListenedAt, locale)}
                      </small>
                    </span>
                    <div className="user-history-row-actions">
                      <button
                        className="text-button"
                        disabled={
                          !item.PlaceId
                          || !item.AudioId
                          || replayingHistoryId === item.ListeningHistoryId
                          || deletingHistoryId !== null
                          || clearingListeningHistory
                        }
                        onClick={() => replayHistoryItem(item)}
                        type="button"
                      >
                        {replayingHistoryId === item.ListeningHistoryId
                          ? t("Đang tải...")
                          : t("Nghe lại")}
                      </button>
                      <button
                        className="text-button danger-text"
                        disabled={
                          deletingHistoryId !== null
                          || clearingListeningHistory
                          || listeningHistoryLoading
                        }
                        onClick={() => deleteListeningHistoryEntry(item)}
                        type="button"
                      >
                        {deletingHistoryId === item.ListeningHistoryId
                          ? t("Đang xóa...")
                          : t("Xóa")}
                      </button>
                    </div>
                  </li>
                ))}
                {listeningHistoryLoading ? (
                  <li className="muted-row">{t("Đang tải lịch sử nghe...")}</li>
                ) : listeningHistory.length === 0 ? (
                  <li className="muted-row">{t("Không có lịch sử nghe.")}</li>
                ) : null}
              </ul>
              {listeningHistoryTotal > LISTENING_HISTORY_PAGE_LIMIT && (
                <div className="user-place-pagination">
                  <button
                    className="button button-outline"
                    disabled={listeningHistoryLoading || listeningHistorySkip === 0}
                    onClick={() => setListeningHistorySkip((current) => (
                      Math.max(0, current - LISTENING_HISTORY_PAGE_LIMIT)
                    ))}
                    type="button"
                  >
                    {t("Trang trước")}
                  </button>
                  <span>
                    Trang {Math.floor(
                      listeningHistorySkip / LISTENING_HISTORY_PAGE_LIMIT,
                    ) + 1} /{" "}
                    {Math.ceil(
                      listeningHistoryTotal / LISTENING_HISTORY_PAGE_LIMIT,
                    )}
                  </span>
                  <button
                    className="button button-outline"
                    disabled={
                      listeningHistoryLoading
                      || listeningHistorySkip + LISTENING_HISTORY_PAGE_LIMIT
                        >= listeningHistoryTotal
                    }
                    onClick={() => setListeningHistorySkip((current) => (
                      current + LISTENING_HISTORY_PAGE_LIMIT
                    ))}
                    type="button"
                  >
                    {t("Trang sau")}
                  </button>
                </div>
              )}
              </div>
              )}
            </section>
          </section>
          )}

      {error && <div className="message message-error" role="alert">{t(error)}</div>}
      {notice && !error && <div className="message message-success" role="status">{t(notice)}</div>}
      {loginPromptOpen && (
        <div
          className="user-login-modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setLoginPromptOpen(false);
            }
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setLoginPromptOpen(false);
            }
          }}
        >
          <section
            aria-labelledby="guest-login-title"
            aria-modal="true"
            className="user-login-modal"
            ref={loginPromptRef}
            role="dialog"
            tabIndex={-1}
          >
            <button
              aria-label={t("Đóng thông báo đăng nhập")}
              className="user-login-modal-close"
              onClick={() => setLoginPromptOpen(false)}
              type="button"
            >
              ×
            </button>
            <p className="eyebrow">{t("SAIGON ECHO · TÀI KHOẢN")}</p>
            <h2 id="guest-login-title">{t("Đăng nhập để lưu địa điểm")}</h2>
            <p>
              {t("Bạn vẫn có thể tiếp tục khám phá và nghe thuyết minh với tư cách khách. Đăng nhập hoặc tạo tài khoản để lưu địa điểm yêu thích.")}
            </p>
            <div className="user-login-modal-actions">
              <button className="button" onClick={goToLogin} type="button">
                {t("Đăng nhập hoặc đăng ký")}
              </button>
              <button
                className="button button-outline"
                onClick={() => setLoginPromptOpen(false)}
                type="button"
              >
                {t("Tiếp tục khám phá")}
              </button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
