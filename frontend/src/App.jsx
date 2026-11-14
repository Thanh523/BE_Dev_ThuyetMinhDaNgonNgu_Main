import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AdminApp from "./AdminApp.jsx";
import UserApp from "./UserApp.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/admin/*" element={<AdminApp />} />
        <Route path="/user/*" element={<UserApp />} />
        <Route path="*" element={<Navigate replace to="/user" />} />
      </Routes>
    </BrowserRouter>
  );
}
