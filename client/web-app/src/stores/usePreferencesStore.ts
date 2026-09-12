import { create } from 'zustand';

export type ThemeMode = 'light' | 'dark' | 'white' | 'black' | 'system';

/**
 * Tông màu — trục RIÊNG, vuông góc với sáng/tối.
 *
 * Gộp vào ThemeMode sẽ nhân đôi số lựa chọn và làm người dùng mất chế độ tối
 * khi đổi tông. Tách ra thì "ngọc bích + tối" là một tổ hợp hợp lệ.
 */
export type PaletteId = 'default' | 'jade' | 'plum' | 'quartz';

export const PALETTES: { id: PaletteId; labelVi: string; labelEn: string; swatch: string }[] = [
  { id: 'default', labelVi: 'Mặc định', labelEn: 'Default', swatch: '#356F83' },
  { id: 'jade', labelVi: 'Ngọc bích', labelEn: 'Jade', swatch: '#2F6B4F' },
  { id: 'plum', labelVi: 'Mận', labelEn: 'Plum', swatch: '#6B3F73' },
  { id: 'quartz', labelVi: 'Thạch anh', labelEn: 'Quartz', swatch: '#5B6C78' },
];
export type LanguageCode = 'en' | 'vi';

export type UserProfile = {
  name: string;
  email: string;
  program: string;
  cohort: string;
  stage: string;
  mentor: string;
  avatarUrl?: string;
};

export type FontSizeScale = 'small' | 'medium' | 'large';

export type AccessibilitySettings = {
  reduceMotion: boolean;
  highContrast: boolean;
  /** Cỡ chữ giao diện: nhỏ / vừa / lớn. */
  fontSize: FontSizeScale;
  /** Giữ để tương thích bản localStorage cũ; đồng bộ theo fontSize. */
  largeText: boolean;
  comfortableSpacing: boolean;
};

export type BriefingPreferences = {
  dailyBriefingEnabled: boolean;
  briefingTime: string;
  /** IANA timezone, ví dụ `Asia/Ho_Chi_Minh`. Backend cần đúng dạng này. */
  timezone: string;
  includeDeadlines: boolean;
  includePossibleTasks: boolean;
  includeSourceCoverage: boolean;
};

/** Báo trước bao lâu cho deliverable/lịch khẩn — chọn ở Onboarding, đọc lại ở Settings/Profile. */
export type ReminderLeadTime = '24h' | '12h' | '2h';

export type NotificationPreferences = {
  urgentDeadlines: boolean;
  importantChanges: boolean;
  sourceConflicts: boolean;
  possibleTasks: boolean;
  connectionIssues: boolean;
  deliveryInApp: boolean;
  deliveryEmail: boolean;
  reminderLeadTime: ReminderLeadTime;
};

type PreferencesStore = {
  theme: ThemeMode;
  setTheme: (theme: ThemeMode) => void;
  palette: PaletteId;
  setPalette: (palette: PaletteId) => void;

  language: LanguageCode;
  setLanguage: (lang: LanguageCode) => void;

  accessibility: AccessibilitySettings;
  updateAccessibility: (settings: Partial<AccessibilitySettings>) => void;

  /** Email user đang gắn workspace local (profile/avatar/onboarding). */
  activeUserKey: string | null;
  profile: UserProfile;
  updateProfile: (profile: Partial<UserProfile>) => void;
  /** Nạp profile + onboarding theo user sau sign-in/sign-up/bootstrap. */
  hydrateForUser: (email: string, seed?: Partial<UserProfile>) => void;
  clearWorkspaceUser: () => void;

  briefingPreferences: BriefingPreferences;
  updateBriefingPreferences: (prefs: Partial<BriefingPreferences>) => void;

  notificationPreferences: NotificationPreferences;
  updateNotificationPreferences: (prefs: Partial<NotificationPreferences>) => void;

  /** true = đã hoàn tất onboarding setup (theo từng user). */
  onboardingDismissed: boolean;
  dismissOnboarding: () => void;

  resetAllPrototypeData: () => void;
};

const WORKSPACE_KEY = 'nav_user_workspace_v1';
const LEGACY_PROFILE_KEY = 'nav_profile';
const LEGACY_ONBOARDING_KEY = 'nav_onboarding_dismissed';

type UserWorkspace = {
  profile: UserProfile;
  onboardingCompleted: boolean;
};

type WorkspaceMap = Record<string, UserWorkspace>;

const EMPTY_PROFILE: UserProfile = {
  name: '',
  email: '',
  program: 'AI Product Development Program',
  cohort: 'Cohort 2026',
  stage: 'AI Innovation Fellow',
  mentor: '',
};

function normalizeUserKey(email: string): string {
  return email.trim().toLowerCase();
}

function readWorkspaceMap(): WorkspaceMap {
  try {
    const raw = localStorage.getItem(WORKSPACE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as WorkspaceMap;
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function writeWorkspaceMap(map: WorkspaceMap): void {
  localStorage.setItem(WORKSPACE_KEY, JSON.stringify(map));
}

function readUserWorkspace(email: string): UserWorkspace | null {
  const key = normalizeUserKey(email);
  if (!key) return null;
  return readWorkspaceMap()[key] ?? null;
}

function writeUserWorkspace(email: string, workspace: UserWorkspace): void {
  const key = normalizeUserKey(email);
  if (!key) return;
  const map = readWorkspaceMap();
  map[key] = workspace;
  writeWorkspaceMap(map);
}

const DEFAULT_ACCESSIBILITY: AccessibilitySettings = {
  reduceMotion: false,
  highContrast: false,
  fontSize: 'medium',
  largeText: false,
  comfortableSpacing: false,
};

function normalizeAccessibility(raw: Partial<AccessibilitySettings> & Record<string, unknown>): AccessibilitySettings {
  const fontSize: FontSizeScale =
    raw.fontSize === 'small' || raw.fontSize === 'medium' || raw.fontSize === 'large'
      ? raw.fontSize
      : raw.largeText
        ? 'large'
        : DEFAULT_ACCESSIBILITY.fontSize;

  return {
    ...DEFAULT_ACCESSIBILITY,
    reduceMotion: Boolean(raw.reduceMotion),
    // Chỉ ghi đè khi user đã từng lưu; lần đầu dùng mặc định high contrast bật.
    highContrast:
      'highContrast' in raw ? Boolean(raw.highContrast) : DEFAULT_ACCESSIBILITY.highContrast,
    comfortableSpacing: Boolean(raw.comfortableSpacing),
    fontSize,
    largeText: fontSize === 'large',
  };
}

const DEFAULT_BRIEFING_PREFS: BriefingPreferences = {
  dailyBriefingEnabled: true,
  briefingTime: '08:00 AM',
  // Program Frame mục 2 chốt Asia/Ho_Chi_Minh là mặc định của chương trình.
  timezone: 'Asia/Ho_Chi_Minh',
  includeDeadlines: true,
  includePossibleTasks: true,
  includeSourceCoverage: true,
};

const DEFAULT_NOTIF_PREFS: NotificationPreferences = {
  urgentDeadlines: true,
  importantChanges: true,
  sourceConflicts: true,
  possibleTasks: true,
  connectionIssues: true,
  deliveryInApp: true,
  deliveryEmail: false,
  reminderLeadTime: '24h',
};

// Helper for initial theme
const getInitialTheme = (): ThemeMode => {
  const saved = localStorage.getItem('nav_theme');
  if (saved === 'light' || saved === 'dark' || saved === 'white' || saved === 'black' || saved === 'system') return saved;
  return 'light';
};

// Helper for initial language
const getInitialPalette = (): PaletteId => {
  const saved = localStorage.getItem('nav_palette');
  return PALETTES.some((item) => item.id === saved) ? (saved as PaletteId) : 'default';
};

// Helper for initial language
const getInitialLanguage = (): LanguageCode => {
  const saved = localStorage.getItem('nav_language');
  if (saved === 'en' || saved === 'vi') return saved;
  return 'vi';
};

export const usePreferencesStore = create<PreferencesStore>((set, get) => ({
  theme: getInitialTheme(),
  setTheme: (theme) => {
    localStorage.setItem('nav_theme', theme);
    set({ theme });
    applyThemeToDOM(theme);
  },

  palette: getInitialPalette(),
  setPalette: (palette) => {
    localStorage.setItem('nav_palette', palette);
    set({ palette });
    applyPaletteToDOM(palette);
  },

  language: getInitialLanguage(),
  setLanguage: (language) => {
    localStorage.setItem('nav_language', language);
    set({ language });
  },

  accessibility: normalizeAccessibility(
    JSON.parse(localStorage.getItem('nav_accessibility') || '{}'),
  ),
  updateAccessibility: (settings) => {
    const merged = { ...get().accessibility, ...settings };
    if (settings.fontSize) {
      merged.largeText = settings.fontSize === 'large';
    } else if (typeof settings.largeText === 'boolean' && !settings.fontSize) {
      merged.fontSize = settings.largeText ? 'large' : 'medium';
      merged.largeText = settings.largeText;
    }
    const updated = normalizeAccessibility(merged);
    localStorage.setItem('nav_accessibility', JSON.stringify(updated));
    set({ accessibility: updated });
    applyAccessibilityToDOM(updated);
  },

  // Chưa hydrate theo session — tránh giữ avatar/profile user trước.
  activeUserKey: null,
  profile: { ...EMPTY_PROFILE },
  updateProfile: (partial) => {
    const prev = get().profile;
    const updated: UserProfile = { ...prev, ...partial };
    if ('avatarUrl' in partial && !partial.avatarUrl) {
      delete updated.avatarUrl;
    }
    const key = get().activeUserKey;
    if (key) {
      writeUserWorkspace(key, {
        profile: updated,
        onboardingCompleted: get().onboardingDismissed,
      });
    }
    set({ profile: updated });
  },
  hydrateForUser: (email, seed = {}) => {
    const key = normalizeUserKey(email);
    if (!key) return;

    let stored = readUserWorkspace(key);
    // Migrate localStorage cũ (một profile chung) chỉ khi email khớp user hiện tại.
    if (!stored) {
      try {
        const legacyRaw = localStorage.getItem(LEGACY_PROFILE_KEY);
        if (legacyRaw) {
          const legacy = JSON.parse(legacyRaw) as Partial<UserProfile>;
          if (legacy.email && normalizeUserKey(legacy.email) === key) {
            stored = {
              profile: { ...EMPTY_PROFILE, ...legacy, email: email.trim() },
              onboardingCompleted: localStorage.getItem(LEGACY_ONBOARDING_KEY) === 'true',
            };
            writeUserWorkspace(key, stored);
          }
        }
      } catch {
        // bỏ qua migrate hỏng
      }
    }

    const baseName =
      seed.name?.trim() ||
      stored?.profile.name?.trim() ||
      email.trim().split('@')[0] ||
      '';

    const profile: UserProfile = {
      ...EMPTY_PROFILE,
      ...(stored?.profile ?? {}),
      ...seed,
      name: baseName,
      email: email.trim(),
    };
    // User mới / chưa từng lưu avatar: không kế thừa avatar trong memory từ session trước.
    if (!stored?.profile?.avatarUrl && !seed.avatarUrl) {
      delete profile.avatarUrl;
    }

    const onboardingCompleted = stored?.onboardingCompleted ?? false;
    writeUserWorkspace(key, { profile, onboardingCompleted });
    set({
      activeUserKey: key,
      profile,
      onboardingDismissed: onboardingCompleted,
    });
  },
  clearWorkspaceUser: () => {
    set({
      activeUserKey: null,
      profile: { ...EMPTY_PROFILE },
      onboardingDismissed: false,
    });
  },

  briefingPreferences: {
    ...DEFAULT_BRIEFING_PREFS,
    ...(JSON.parse(localStorage.getItem('nav_briefing_prefs') || '{}')),
  },
  updateBriefingPreferences: (prefs) => {
    const updated = { ...get().briefingPreferences, ...prefs };
    localStorage.setItem('nav_briefing_prefs', JSON.stringify(updated));
    set({ briefingPreferences: updated });
  },

  notificationPreferences: {
    ...DEFAULT_NOTIF_PREFS,
    ...(JSON.parse(localStorage.getItem('nav_notif_prefs') || '{}')),
  },
  updateNotificationPreferences: (prefs) => {
    const updated = { ...get().notificationPreferences, ...prefs };
    localStorage.setItem('nav_notif_prefs', JSON.stringify(updated));
    set({ notificationPreferences: updated });
  },

  onboardingDismissed: false,
  dismissOnboarding: () => {
    const key = get().activeUserKey;
    if (key) {
      writeUserWorkspace(key, {
        profile: get().profile,
        onboardingCompleted: true,
      });
    }
    set({ onboardingDismissed: true });
  },

  resetAllPrototypeData: () => {
    localStorage.clear();
    set({
      theme: 'light',
      palette: 'default',
      language: 'vi',
      accessibility: DEFAULT_ACCESSIBILITY,
      activeUserKey: null,
      profile: { ...EMPTY_PROFILE },
      briefingPreferences: DEFAULT_BRIEFING_PREFS,
      notificationPreferences: DEFAULT_NOTIF_PREFS,
      onboardingDismissed: false,
    });
    applyThemeToDOM('light');
    applyAccessibilityToDOM(DEFAULT_ACCESSIBILITY);
  },
}));

// Apply theme to html element
export function applyThemeToDOM(mode: ThemeMode) {
  const root = document.documentElement;
  let isDark = mode === 'dark' || mode === 'black';
  if (mode === 'system') {
    isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  }
  if (isDark) {
    root.setAttribute('data-theme', mode === 'black' ? 'black' : 'dark');
    root.classList.add('dark');
  } else {
    root.setAttribute('data-theme', mode === 'white' ? 'white' : 'light');
    root.classList.remove('dark');
  }
}

/**
 * Tông mặc định KHÔNG đặt thuộc tính: bộ token gốc nằm ở `[data-theme=...]`,
 * thêm `data-palette="default"` chỉ tạo một nhánh CSS rỗng phải nhớ duy trì.
 */
export function applyPaletteToDOM(palette: PaletteId) {
  const root = document.documentElement;
  if (palette === 'default') root.removeAttribute('data-palette');
  else root.setAttribute('data-palette', palette);
}

// Apply accessibility classes to html element
export function applyAccessibilityToDOM(acc: AccessibilitySettings) {
  const root = document.documentElement;
  if (acc.reduceMotion) root.classList.add('reduce-motion');
  else root.classList.remove('reduce-motion');

  if (acc.highContrast) root.classList.add('high-contrast');
  else root.classList.remove('high-contrast');

  // text-size-* trên html: Tailwind rem (Briefing History, Settings, …) đổi theo S/M/L.
  // Landing được chống lại bằng zoom trong index.css.
  root.classList.remove('text-size-sm', 'text-size-md', 'text-size-lg', 'large-text');
  if (acc.fontSize === 'small') root.classList.add('text-size-sm');
  else if (acc.fontSize === 'large') root.classList.add('text-size-lg', 'large-text');
  else root.classList.add('text-size-md');

  if (acc.comfortableSpacing) root.classList.add('comfortable-spacing');
  else root.classList.remove('comfortable-spacing');
}

// Initialize on script load
if (typeof window !== 'undefined') {
  applyThemeToDOM(getInitialTheme());
  const initialAcc = normalizeAccessibility(
    JSON.parse(localStorage.getItem('nav_accessibility') || '{}'),
  );
  applyAccessibilityToDOM(initialAcc);
}
