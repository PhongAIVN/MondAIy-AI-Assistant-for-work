"""Trang cứu hộ PWA đi thẳng qua network.

Service worker của web app cố ý bỏ qua ``/api/*``. Vì vậy endpoint này vẫn mở
được ngay cả khi một service worker cũ đang giữ ``index.html``/bundle hỏng và
mọi route giao diện khác chỉ hiện nền trống.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/pwa", tags=["pwa-recovery"])


@router.get("/recover", response_class=HTMLResponse, include_in_schema=False)
def recover_pwa() -> HTMLResponse:
    """Xóa SW/cache tĩnh của đúng origin rồi quay lại workspace.

    Không xóa localStorage/sessionStorage nên phiên đăng nhập vẫn được giữ.
    HTML dùng JavaScript cú pháp cũ để chạy được cả trên WebKit đời cũ.
    """
    html = """<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="theme-color" content="#356F83">
  <title>Khôi phục mondaiy</title>
  <style>
    html,body{margin:0;min-height:100%;background:#ffffdd;color:#173a49;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    main{min-height:100vh;min-height:100dvh;box-sizing:border-box;display:flex;align-items:center;justify-content:center;padding:max(28px,env(safe-area-inset-top)) 24px max(28px,env(safe-area-inset-bottom));text-align:center}
    section{max-width:360px}h1{font-size:23px;margin:0 0 10px}p{font-size:14px;line-height:1.55;color:#55717c;margin:0}
    button{width:100%;margin-top:20px;border:0;border-radius:12px;padding:12px 16px;background:#356f83;color:#fff;font:inherit;font-weight:700}
  </style>
</head>
<body>
<main><section role="status" aria-live="polite">
  <h1>Đang làm mới mondaiy…</h1>
  <p id="message">Ứng dụng đang xóa phiên bản PWA cũ trên thiết bị này. Tài khoản của bạn vẫn được giữ nguyên.</p>
  <button id="retry" type="button" hidden>Thử lại</button>
</section></main>
<script>
(function () {
  var message = document.getElementById('message');
  var retry = document.getElementById('retry');
  function finish() {
    // unregister() không giải phóng document hiện tại ngay: controller cũ còn
    // sống đến khi client unload. Đi qua một document /api thứ hai (vốn luôn
    // nằm ngoài NavigationRoute cũ) trước khi quay lại app.
    window.location.replace('/api/v1/pwa/recover?clean=1&ts=' + Date.now());
  }
  function recover() {
    retry.hidden = true;
    message.textContent = 'Ứng dụng đang xóa phiên bản PWA cũ trên thiết bị này. Tài khoản của bạn vẫn được giữ nguyên.';
    var jobs = [];
    try {
      if (navigator.serviceWorker && navigator.serviceWorker.getRegistrations) {
        jobs.push(navigator.serviceWorker.getRegistrations().then(function (items) {
          return Promise.all(items.map(function (item) { return item.unregister(); }));
        }));
      }
      if (window.caches && window.caches.keys) {
        jobs.push(window.caches.keys().then(function (keys) {
          return Promise.all(keys.map(function (key) { return window.caches.delete(key); }));
        }));
      }
      Promise.all(jobs).then(function () { setTimeout(finish, 250); }, function () {
        message.textContent = 'Chưa xóa được dữ liệu PWA cũ. Hãy thử lại một lần nữa.';
        retry.hidden = false;
      });
    } catch (error) {
      message.textContent = 'Chưa xóa được dữ liệu PWA cũ. Hãy thử lại một lần nữa.';
      retry.hidden = false;
    }
  }
  retry.onclick = recover;
  if (window.location.search.indexOf('clean=1') !== -1) {
    if (navigator.serviceWorker && navigator.serviceWorker.controller) {
      message.textContent = 'Đã xóa bản PWA cũ. Hãy đóng hẳn mondaiy khỏi màn hình đa nhiệm rồi mở lại từ Home Screen.';
      retry.textContent = 'Mở lại mondaiy';
      retry.hidden = false;
      retry.onclick = function () { window.location.replace('/briefing?pwaRecovered=' + Date.now()); };
    } else {
      message.textContent = 'Đã làm mới xong. Đang mở lại mondaiy…';
      setTimeout(function () { window.location.replace('/briefing?pwaRecovered=' + Date.now()); }, 350);
    }
  } else {
    recover();
  }
}());
</script>
</body>
</html>"""
    return HTMLResponse(
        content=html,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )
