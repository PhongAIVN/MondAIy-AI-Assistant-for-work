import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from '../i18n/useTranslation';
import { usePreferencesStore } from '../stores/usePreferencesStore';
import { useAuthStore } from '../stores/useAuthStore';
import { useAppStore } from '../stores/useAppStore';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Toggle } from '../components/ui/Toggle';
import { UserAvatar } from '../components/ui/UserAvatar';
import {
  User,
  Clock,
  Edit3,
  Camera,
  Trash2,
} from 'lucide-react';

const MAX_AVATAR_BYTES = 1.5 * 1024 * 1024;

export const ProfilePage: React.FC = () => {
  const { t } = useTranslation();
  const { addToast } = useAppStore();
  const googleAvatarUrl = useAuthStore((state) => state.user?.avatarUrl);
  const {
    profile,
    updateProfile,
    briefingPreferences,
    updateBriefingPreferences,
  } = usePreferencesStore();

  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState(profile);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isEditing) setFormData(profile);
  }, [profile, isEditing]);

  const handleSaveProfile = () => {
    updateProfile(formData);
    setIsEditing(false);
    addToast({
      type: 'success',
      title: t.profilePage.profileSaved,
      message: t.profilePage.profileSavedMsg,
    });
  };

  const handleAvatarPick = () => fileInputRef.current?.click();

  const handleAvatarFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      addToast({
        type: 'error',
        title: t.profilePage.changeAvatar,
        message: t.profilePage.avatarInvalid,
      });
      return;
    }

    if (file.size > MAX_AVATAR_BYTES) {
      addToast({
        type: 'error',
        title: t.profilePage.changeAvatar,
        message: t.profilePage.avatarTooLarge,
      });
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const avatarUrl = typeof reader.result === 'string' ? reader.result : '';
      if (!avatarUrl) return;
      updateProfile({ avatarUrl });
      setFormData((prev) => ({ ...prev, avatarUrl }));
      addToast({
        type: 'success',
        title: t.profilePage.avatarUpdated,
        message: t.profilePage.avatarUpdatedMsg,
      });
    };
    reader.readAsDataURL(file);
  };

  const handleRemoveAvatar = () => {
    updateProfile({ avatarUrl: undefined });
    setFormData((prev) => ({ ...prev, avatarUrl: undefined }));
    addToast({
      type: 'info',
      title: t.profilePage.avatarRemoved,
      message: t.profilePage.avatarRemovedMsg,
    });
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-[var(--color-primary)] mb-1">
            <User className="w-4 h-4" /> {t.profilePage.eyebrow}
          </div>
          <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] font-heading">
            {t.profilePage.title}
          </h1>
          <p className="text-xs text-[var(--color-text-secondary)] mt-1">{t.profilePage.subtitle}</p>
        </div>

        <Button
          variant={isEditing ? 'primary' : 'outline'}
          size="md"
          icon={<Edit3 className="w-4 h-4" />}
          onClick={() => {
            if (isEditing) handleSaveProfile();
            else setIsEditing(true);
          }}
        >
          {isEditing ? t.actions.save : t.profilePage.editProfile}
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="space-y-4 text-center md:text-left">
          <div className="flex flex-col items-center md:items-start gap-3">
            <div className="relative">
              <UserAvatar
                name={profile.name}
                avatarUrl={profile.avatarUrl || googleAvatarUrl}
                size="xl"
              />
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif"
                className="sr-only"
                onChange={handleAvatarFile}
              />
              <button
                type="button"
                onClick={handleAvatarPick}
                className="absolute bottom-0 right-0 p-1.5 bg-[#2563A6] text-white rounded-full border-2 border-white hover:bg-[#0F1F38] transition-colors"
                title={t.profilePage.changeAvatar}
                aria-label={t.profilePage.changeAvatar}
              >
                <Camera className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="flex items-center gap-2 flex-wrap justify-center md:justify-start">
              <Button variant="outline" size="sm" icon={<Camera className="w-3.5 h-3.5" />} onClick={handleAvatarPick}>
                {t.profilePage.changeAvatar}
              </Button>
              {profile.avatarUrl && (
                <Button
                  variant="ghost"
                  size="sm"
                  icon={<Trash2 className="w-3.5 h-3.5" />}
                  onClick={handleRemoveAvatar}
                >
                  {t.profilePage.removeAvatar}
                </Button>
              )}
            </div>

            <div>
              {isEditing ? (
                <div className="space-y-2 mt-1 w-full">
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-lg font-bold"
                  />
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-lg"
                  />
                </div>
              ) : (
                <>
                  <h2 className="text-lg font-extrabold text-[var(--color-text-primary)] font-heading">
                    {profile.name}
                  </h2>
                  <p className="text-xs text-[var(--color-text-secondary)]">{profile.email}</p>
                </>
              )}
            </div>
          </div>
        </Card>

        {/* Right Column: Preferences */}
        <div className="md:col-span-2 space-y-6">
          {/* Briefing Preferences */}
          <Card className="space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-3">
              <div className="flex items-center gap-2">
                <Clock className="w-5 h-5 text-[var(--color-primary)]" />
                <h3 className="text-base font-bold text-[var(--color-text-primary)] font-heading">
                  {t.profilePage.briefingPreferences}
                </h3>
              </div>
            </div>

            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between p-3 bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-xl">
                <div>
                  <span className="font-bold text-[var(--color-text-primary)] block">
                    {t.profilePage.dailyBriefingEnabled}
                  </span>
                  <span className="text-[var(--color-text-secondary)] text-[11px]">
                    {t.profilePage.dailyBriefingHint}
                  </span>
                </div>
                <Toggle
                  checked={briefingPreferences.dailyBriefingEnabled}
                  onChange={(checked) =>
                    updateBriefingPreferences({ dailyBriefingEnabled: checked })
                  }
                  aria-label={t.profilePage.dailyBriefingEnabled}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="p-3 bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-xl space-y-1">
                  <label className="font-bold text-[var(--color-text-primary)] block">
                    {t.profilePage.briefingTime}
                  </label>
                  <select
                    value={briefingPreferences.briefingTime}
                    onChange={(e) =>
                      updateBriefingPreferences({ briefingTime: e.target.value })
                    }
                    className="w-full p-1.5 text-xs bg-[var(--color-surface-muted)] border border-[var(--color-border)] rounded-lg font-semibold"
                  >
                    <option value="07:00 AM">07:00 AM</option>
                    <option value="08:00 AM">08:00 AM</option>
                    <option value="09:00 AM">09:00 AM</option>
                  </select>
                </div>

                <div className="p-3 bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-xl space-y-1">
                  <label className="font-bold text-[var(--color-text-primary)] block">
                    {t.profilePage.timezone}
                  </label>
                  <select
                    value={briefingPreferences.timezone}
                    onChange={(e) => updateBriefingPreferences({ timezone: e.target.value })}
                    className="w-full p-1.5 text-xs bg-[var(--color-surface-muted)] border border-[var(--color-border)] rounded-lg font-semibold"
                  >
                    <option value="Asia/Ho_Chi_Minh">Asia/Ho_Chi_Minh (ICT, UTC+07:00)</option>
                    <option value="Asia/Bangkok">Asia/Bangkok (ICT, UTC+07:00)</option>
                    <option value="Asia/Singapore">Asia/Singapore (UTC+08:00)</option>
                    <option value="Asia/Tokyo">Asia/Tokyo (UTC+09:00)</option>
                    <option value="Europe/London">Europe/London (UTC+00:00)</option>
                    <option value="America/New_York">America/New_York (UTC-05:00)</option>
                  </select>
                </div>
              </div>

              <div className="space-y-2 pt-2">
                {[
                  {
                    key: 'includeDeadlines',
                    label: t.profilePage.includeDeadlines,
                    val: briefingPreferences.includeDeadlines,
                  },
                  {
                    key: 'includePossibleTasks',
                    label: t.profilePage.includePossibleTasks,
                    val: briefingPreferences.includePossibleTasks,
                  },
                  {
                    key: 'includeSourceCoverage',
                    label: t.profilePage.includeSourceCoverage,
                    val: briefingPreferences.includeSourceCoverage,
                  },
                ].map((item) => (
                  <div
                    key={item.key}
                    className="flex items-center justify-between gap-3 text-[var(--color-text-secondary)]"
                  >
                    <span className="text-[var(--color-text-primary)]">{item.label}</span>
                    <Toggle
                      checked={item.val}
                      onChange={(checked) =>
                        updateBriefingPreferences({ [item.key]: checked })
                      }
                      aria-label={item.label}
                    />
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};
