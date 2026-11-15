import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

const AdminApp = lazy(() => import("./AdminApp.jsx"));
const UserApp = lazy(() => import("./UserApp.jsx"));

function RouteLoading() {
  return (
    <main className="route-loading" aria-live="polite">
      <div className="route-loading-mark" aria-hidden="true">SE</div>
      <p>Đang mở không gian Saigon Echo...</p>
    </main>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<RouteLoading />}>
        <Routes>
          <Route path="/admin/*" element={<AdminApp />} />
          <Route path="/user/*" element={<UserApp />} />
          <Route path="*" element={<Navigate replace to="/user" />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
