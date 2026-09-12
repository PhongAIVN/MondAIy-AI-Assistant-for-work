# web-app

React + TypeScript + Vite + Tailwind CSS. Giao diện user và admin cho SocialMind AI, nằm trong `client/` cùng `client/extension` (browser extension) và `client/web` (thiết kế UI).

> **Draft, chưa Approved.** Flow điều hướng và câu hỏi mở về scope (đặc biệt
> phần `/admin`) đang ở [ui-flow.md mục 13](../../docs/projects/design/ui-flow.md#13-web-app--user--admin-surface-draft-nhánh-uiux)
> và [web-app-ui-flow.mmd](../../docs/projects/design/web-app-ui-flow.mmd) —
> cần PM + Technical Lead review trước khi coi đây là product surface chính thức.

## Yêu cầu

- Node.js 18+
- npm

## Chạy dự án

```bash
cd client/web-app
npm install
npm run dev       # dev server, mặc định http://localhost:5173
npm run build     # build production vào dist/
npm run preview   # xem thử bản build
npm run lint      # oxlint
```

## Cấu trúc thư mục

```
src/
  App.tsx              # khai báo route (react-router-dom), BrowserRouter gốc
  main.tsx             # entry point
  index.css            # Tailwind import + CSS variables (theme sáng/tối)

  layouts/              # layout khung cũ (không còn dùng, giữ tham khảo)

  components/
    layout/             # khung trang: MarketingLayout, AuthLayout, AppShell (user), AdminShell (admin)
    auth/               # ProtectedRoute — chặn route theo role (participant/mentor/admin)
    ui/                 # component dùng chung: Button, Badge, Card, Dialog, Drawer, Toast...
    briefing/           # component cho luồng Daily Briefing (card, modal review/feedback)
    navigator/          # component chat "Navigator" (drawer trợ lý AI nổi)

  pages/
    marketing/          # LandingPage — trang công khai "/"
    auth/                # SignIn, SignUp, ForgotPassword, ResetPassword
    admin/               # toàn bộ trang trong "/admin" (Dashboard, Users, Programs, Sources...)
    *.tsx                # trang user đã đăng nhập: DailyBriefing, Tasks, Calendar, SourceLibrary,
                          # Activity, Notifications, Settings, Profile, Help, Onboarding

  stores/               # zustand store: useAuthStore, useAppStore, useBriefingStore,
                         # useNavigatorStore, usePreferencesStore (theme/ngôn ngữ)
  data/                 # mock data dùng khi chưa nối API thật
  i18n/                 # bản dịch (vi/en) + hook useTranslation
  types/                # type dùng chung (briefing, task, source, activity)
```

## Routing tổng quan (`src/App.tsx`)

| Path | Layout | Ghi chú |
|---|---|---|
| `/` | MarketingLayout | trang giới thiệu công khai |
| `/sign-in`, `/sign-up`, `/forgot-password`, `/reset-password` | AuthLayout | công khai |
| `/briefing`, `/tasks`, `/calendar`, `/sources`, `/activity`, `/notifications`, `/settings`, `/profile`, `/help`, `/onboarding` | AppShell | cần đăng nhập (`ProtectedRoute`) |
| `/admin`, `/admin/*` | AdminShell | cần role `admin` (`ProtectedRoute`) |

Hiện tại auth/data đang dùng mock (`stores/`, `data/`) — chưa nối API backend ở `src/api` (Python/FastAPI) của repo gốc.
