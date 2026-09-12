import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './stores/useAuthStore';

// Layouts
import { AppShell } from './components/layout/AppShell';
import { MarketingLayout } from './components/layout/MarketingLayout';
import { AuthLayout } from './components/layout/AuthLayout';
import { AdminShell } from './components/layout/AdminShell';

// Auth Protection Wrapper
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { GuestRoute } from './components/auth/GuestRoute';

// Public Marketing Page
import { LandingPage } from './pages/marketing/LandingPage';
import { BlogPage } from './pages/marketing/BlogPage';
import { BlogPostPage } from './pages/marketing/BlogPostPage';
import { PolicyPage } from './pages/marketing/PolicyPage';
import { TermsPage } from './pages/marketing/TermsPage';
import { MarketingHelpPage } from './pages/marketing/MarketingHelpPage';
import { ExtensionInstallPage } from './pages/marketing/ExtensionInstallPage';
import { TryChatPage } from './pages/marketing/TryChatPage';

// Auth Pages
import { SignInPage } from './pages/auth/SignInPage';
import { SignUpPage } from './pages/auth/SignUpPage';
import { ForgotPasswordPage } from './pages/auth/ForgotPasswordPage';
import { ResetPasswordPage } from './pages/auth/ResetPasswordPage';
import { GoogleCallbackPage } from './pages/auth/GoogleCallbackPage';

// User Workspace Pages
import { DailyBriefingPage } from './pages/DailyBriefingPage';
import { TasksPage } from './pages/TasksPage';
import { PlannerPage } from './pages/PlannerPage';
import { MeetingNotesPage } from './pages/MeetingNotesPage';
import { MeetingNoteDetailPage } from './pages/MeetingNoteDetailPage';
import { ProjectDetailPage } from './pages/ProjectDetailPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { SourceLibraryPage } from './pages/SourceLibraryPage';
import { DataPrivacyPage } from './pages/DataPrivacyPage';
import { NotificationsPage } from './pages/NotificationsPage';
import { RoutineDetailPage } from './pages/RoutineDetailPage';
import { RoutinesPage } from './pages/RoutinesPage';
import { SettingsPage } from './pages/SettingsPage';
import { ProfilePage } from './pages/ProfilePage';
import { OnboardingPage } from './pages/OnboardingPage';
import { SharedChatPage } from './pages/SharedChatPage';

// Admin Portal Pages
import { AdminDashboardPage } from './pages/admin/AdminDashboardPage';
import { AdminUsersPage } from './pages/admin/AdminUsersPage';
import { AdminProgramsPage } from './pages/admin/AdminProgramsPage';
import { AdminProgramEventsPage } from './pages/admin/AdminProgramEventsPage';
import { AdminSourcesPage } from './pages/admin/AdminSourcesPage';
import { AdminBriefingsPage } from './pages/admin/AdminBriefingsPage';
import { AdminConflictsPage } from './pages/admin/AdminConflictsPage';
import { AdminFeedbackPage } from './pages/admin/AdminFeedbackPage';
import { AdminActivityPage } from './pages/admin/AdminActivityPage';
import { AdminBlogPage } from './pages/admin/AdminBlogPage';
import { AdminSettingsPage } from './pages/admin/AdminSettingsPage';
import { AdminDiscordAnnouncementPage } from './pages/admin/AdminDiscordAnnouncementPage';

export default function App() {
  const bootstrap = useAuthStore((state) => state.bootstrap);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="shared-chat/:token" element={<SharedChatPage />} />
        {/* Public Marketing Route */}
        <Route path="/" element={<MarketingLayout />}>
          {/* Đã đăng nhập mà trỏ về "/" thì vào thẳng /briefing, không thấy landing page nữa. */}
          <Route
            index
            element={
              <GuestRoute>
                <LandingPage />
              </GuestRoute>
            }
          />
          {/* /landing xem được cả khi đã đăng nhập — không qua GuestRoute. */}
          <Route path="landing" element={<LandingPage />} />
          <Route path="blog" element={<BlogPage />} />
          <Route path="blog/:slug" element={<BlogPostPage />} />
          <Route path="policy" element={<PolicyPage />} />
          <Route path="terms" element={<TermsPage />} />
          <Route path="try" element={<TryChatPage />} />
          <Route path="help" element={<MarketingHelpPage />} />
          <Route path="extension" element={<ExtensionInstallPage />} />
        </Route>

        {/* Auth Routes — đã có token hợp lệ thì GuestRoute tự đưa về /briefing */}
        <Route
          element={
            <GuestRoute>
              <AuthLayout />
            </GuestRoute>
          }
        >
          <Route path="sign-in" element={<SignInPage />} />
          <Route path="sign-up" element={<SignUpPage />} />
          <Route path="forgot-password" element={<ForgotPasswordPage />} />
          <Route path="reset-password" element={<ResetPasswordPage />} />
          <Route path="auth/google/callback" element={<GoogleCallbackPage />} />
        </Route>

        {/* Protected User Workspace */}
        <Route
          element={
            <ProtectedRoute allowedRoles={['participant', 'mentor', 'admin']}>
              <AppShell />
            </ProtectedRoute>
          }
        >
          <Route path="briefing" element={<DailyBriefingPage />} />
          <Route path="briefing/conversation/:conversationId" element={<DailyBriefingPage />} />
          <Route path="tasks" element={<TasksPage />} />
          <Route path="planner" element={<PlannerPage />} />
          <Route path="meeting-notes" element={<MeetingNotesPage />} />
          <Route path="meeting-notes/:noteId" element={<MeetingNoteDetailPage />} />
          <Route path="projects" element={<ProjectsPage />} />
          <Route path="projects/:projectId" element={<ProjectDetailPage />} />
          <Route path="sources" element={<SourceLibraryPage />} />
          <Route path="data-privacy" element={<DataPrivacyPage />} />
          <Route path="data-privacy/:tab" element={<DataPrivacyPage />} />
          <Route path="notifications" element={<NotificationsPage />} />
          <Route path="routines" element={<RoutinesPage />} />
          <Route path="routines/:routineId" element={<RoutineDetailPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="onboarding" element={<OnboardingPage />} />
        </Route>

        {/* Protected Admin Portal */}
        <Route
          path="admin"
          element={
            <ProtectedRoute allowedRoles={['admin']} skipOnboardingGate>
              <AdminShell />
            </ProtectedRoute>
          }
        >
          <Route index element={<AdminDashboardPage />} />
          <Route path="users" element={<AdminUsersPage />} />
          <Route path="programs" element={<AdminProgramsPage />} />
          <Route path="programs/:id" element={<Navigate to="/admin/programs" replace />} />
          <Route path="program-events" element={<AdminProgramEventsPage />} />
          <Route path="discord-announcements" element={<AdminDiscordAnnouncementPage />} />
          <Route path="sources" element={<AdminSourcesPage />} />
          <Route path="briefings" element={<AdminBriefingsPage />} />
          <Route path="conflicts" element={<AdminConflictsPage />} />
          <Route path="feedback" element={<AdminFeedbackPage />} />
          <Route path="blog" element={<AdminBlogPage />} />
          <Route path="activity" element={<AdminActivityPage />} />
          <Route path="settings" element={<AdminSettingsPage />} />
        </Route>

        {/* Fallback Catch-all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
