import { readWebSessionFromPage } from "@/lib/webSession";

export default defineContentScript({
  matches: [`${import.meta.env.WXT_WEB_APP_URL}/*`],
  main() {
    function report(): void {
      void chrome.runtime.sendMessage({
        type: "mondaiy-web-session",
        session: readWebSessionFromPage(),
      });
    }

    report();

    // storage event chỉ bắn ở tab KHÁC cùng origin — bắt trường hợp đăng
    // nhập/đăng xuất diễn ra ở tab web app khác, tab này vẫn đang mở.
    window.addEventListener("storage", (event) => {
      if (event.key === "nav_session" || event.key === null) report();
    });

    // Quay lại tab sau khi đăng nhập/đăng xuất ngay trong chính tab này —
    // storage event không bắn cho thay đổi tự thân tab, nên bù bằng visibility.
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") report();
    });
  },
});
