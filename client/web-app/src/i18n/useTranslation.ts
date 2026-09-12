import { usePreferencesStore } from '../stores/usePreferencesStore';
import { translations, type TranslationKeys } from './translations';

export function useTranslation() {
  const language = usePreferencesStore((state) => state.language);
  const t: TranslationKeys = translations[language] || translations.en;
  return { t, language };
}

/** Đọc bản dịch ngoài React (vd. Zustand store) theo ngôn ngữ đang lưu. */
export function getTranslations(): TranslationKeys {
  const language = usePreferencesStore.getState().language;
  return translations[language] || translations.vi;
}
