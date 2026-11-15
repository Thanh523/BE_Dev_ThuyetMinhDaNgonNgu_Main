import { QRCodeSVG } from "qrcode.react";

function getUserPortalUrl() {
  return new URL("/user", window.location.href).toString();
}

export default function UserPortalQr() {
  const userPortalUrl = getUserPortalUrl();
  const localHostname = ["localhost", "127.0.0.1", "::1"].includes(
    window.location.hostname,
  );

  return (
    <aside aria-labelledby="user-portal-qr-title" className="user-portal-qr panel">
      <p className="eyebrow">SAIGON ECHO</p>
      <h2 id="user-portal-qr-title">Quét mã QR để mở trang User</h2>
      <p>Dùng điện thoại quét mã để truy cập trang dành cho người dùng.</p>
      <QRCodeSVG
        aria-label="Mã QR truy cập User Portal"
        bgColor="#ffffff"
        className="user-portal-qr-code"
        fgColor="#17231d"
        includeMargin
        level="M"
        size={184}
        title="Mã QR truy cập User Portal"
        value={userPortalUrl}
      />
      <a className="user-portal-qr-url" href={userPortalUrl}>
        {userPortalUrl}
      </a>
      {localHostname && (
        <p className="user-portal-qr-warning" role="note">
          Địa chỉ localhost chỉ dùng được trên máy này. Để quét bằng điện thoại,
          hãy mở trang bằng tên miền hoặc địa chỉ mạng có thể truy cập từ điện thoại.
        </p>
      )}
    </aside>
  );
}
