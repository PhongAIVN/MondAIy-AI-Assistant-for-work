import React, { useState } from 'react';
import { Activity, Bell, Database, ExternalLink, Gauge, Save, Server, Shield } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { Button } from '../../components/ui/Button';
import { AdminMockBanner } from '../../components/admin/AdminStates';

const GRAFANA_URL = (import.meta.env.VITE_GRAFANA_URL as string | undefined)?.trim();
const PROMETHEUS_URL = (import.meta.env.VITE_PROMETHEUS_URL as string | undefined)?.trim();

type ObservabilityLinkProps = {
  title: string;
  description: string;
  url?: string;
  icon: React.ElementType;
  fallback: string;
};

const ObservabilityLink: React.FC<ObservabilityLinkProps> = ({
  title,
  description,
  url,
  icon: Icon,
  fallback,
}) => (
  <div className="rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] p-4 flex items-start justify-between gap-4">
    <div className="flex items-start gap-3 min-w-0">
      <Icon className="w-4 h-4 text-[#2563A6] mt-0.5 shrink-0" />
      <div className="min-w-0">
        <p className="text-xs font-bold text-[#0F1F38] dark:text-white">{title}</p>
        <p className="text-[11px] text-[#5A6A85] dark:text-[#8B98AB] mt-1">{description}</p>
        <p className="text-[10px] text-[#5A6A85] dark:text-[#8B98AB] mt-2 truncate">
          {url || fallback}
        </p>
      </div>
    </div>
    {url ? (
      <a
        href={url}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1.5 shrink-0 px-3 py-1.5 rounded-lg bg-[#2563A6] text-white text-[11px] font-bold hover:bg-[#1D4F87] transition-colors"
      >
        Mở <ExternalLink className="w-3 h-3" />
      </a>
    ) : (
      <span className="shrink-0 px-3 py-1.5 rounded-lg bg-[#EDF2FB] dark:bg-[#0A1628] text-[#5A6A85] text-[11px] font-semibold">
        Chưa cấu hình
      </span>
    )}
  </div>
);

export const AdminSettingsPage: React.FC = () => {
  const { t } = useTranslation();
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <AdminMockBanner lyDo="Cấu hình hệ thống hiện đọc từ .env, chưa có API đọc/ghi kèm versioning và audit — xem TODO.md." />

      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-[#0F1F38] dark:text-white tracking-tight">
          {t.admin.settings}
        </h1>
        <p className="text-xs text-[#5A6A85] dark:text-[#8B98AB]">
          Configure program organization defaults, briefing generation rules, and audit retention.
        </p>
      </div>

      {saved && (
        <div className="p-3 text-xs rounded-xl bg-emerald-50 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-200">
          Admin prototype settings saved successfully.
        </div>
      )}

      {/* Organization */}
      <div className="p-6 rounded-2xl bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1A2A42] space-y-4">
        <h3 className="font-bold text-sm text-[#0F1F38] dark:text-white flex items-center gap-2">
          <Shield className="w-4 h-4 text-[#2563A6]" />
          <span>Organization & Platform Identity</span>
        </h3>

        <div className="grid sm:grid-cols-2 gap-4 text-xs">
          <div>
            <label className="block font-semibold mb-1">Organization Name</label>
            <input type="text" defaultValue="Global AI Scholar Program" className="w-full p-2.5 rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] bg-white dark:bg-[#0A1628]" />
          </div>
          <div>
            <label className="block font-semibold mb-1">Admin Contact Email</label>
            <input type="email" defaultValue="admin@programnavigator.ai" className="w-full p-2.5 rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] bg-white dark:bg-[#0A1628]" />
          </div>
        </div>
      </div>

      {/* Briefing Generation Defaults */}
      <div className="p-6 rounded-2xl bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1A2A42] space-y-4">
        <h3 className="font-bold text-sm text-[#0F1F38] dark:text-white flex items-center gap-2">
          <Bell className="w-4 h-4 text-[#2563A6]" />
          <span>Briefing Generation Defaults</span>
        </h3>

        <div className="space-y-3 text-xs">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" defaultChecked className="rounded text-[#2563A6]" />
            <span>Enforce mandatory confidence label verification for all AI task extractions</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" defaultChecked className="rounded text-[#2563A6]" />
            <span>Require explicit mentor note before resolving high-severity source conflicts</span>
          </label>
        </div>
      </div>

      {/* Data Retention */}
      <div className="p-6 rounded-2xl bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1A2A42] space-y-4">
        <h3 className="font-bold text-sm text-[#0F1F38] dark:text-white flex items-center gap-2">
          <Database className="w-4 h-4 text-[#2563A6]" />
          <span>Audit Log Retention</span>
        </h3>

        <div className="text-xs">
          <label className="block font-semibold mb-1">Audit Log Retention Window</label>
          <select className="p-2.5 rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] bg-white dark:bg-[#0A1628] font-medium">
            <option>90 Days (Recommended)</option>
            <option>180 Days</option>
            <option>365 Days</option>
          </select>
        </div>
      </div>

      {/* Observability */}
      <div className="p-6 rounded-2xl bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1A2A42] space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="font-bold text-sm text-[#0F1F38] dark:text-white flex items-center gap-2">
              <Activity className="w-4 h-4 text-[#2563A6]" />
              <span>Observability & System Monitoring</span>
            </h3>
            <p className="text-[11px] text-[#5A6A85] dark:text-[#8B98AB] mt-1">
              Theo dõi VM, container, API health, latency và hành vi sản phẩm đã được ẩn danh.
              Các dashboard bên ngoài mở ở tab mới.
            </p>
          </div>
          <Server className="w-5 h-5 text-[#5A6A85] shrink-0" />
        </div>

        <div className="grid md:grid-cols-2 gap-3">
          <ObservabilityLink
            title="Grafana — VM & application dashboards"
            description="CPU, RAM, disk, network, uptime, API latency và alert production."
            url={GRAFANA_URL}
            icon={Gauge}
            fallback="VITE_GRAFANA_URL chưa được cấu hình"
          />
          <ObservabilityLink
            title="Prometheus — metrics & targets"
            description="Kiểm tra targets, scrape health và truy vấn metrics thô."
            url={PROMETHEUS_URL}
            icon={Activity}
            fallback="VITE_PROMETHEUS_URL chưa được cấu hình"
          />
          <ObservabilityLink
            title="User interactions & product telemetry"
            description="Số lượt hỏi, trả lời, feedback và độ trễ; không hiển thị nội dung riêng tư."
            url="/admin/feedback"
            icon={Activity}
            fallback=""
          />
          <ObservabilityLink
            title="Admin audit trail"
            description="Ai thay đổi quyền hoặc trạng thái bản ghi nào, vào thời điểm nào."
            url="/admin/activity"
            icon={Shield}
            fallback=""
          />
        </div>

        <p className="text-[10px] text-[#5A6A85] dark:text-[#8B98AB]">
          Cấu hình URL bằng <code className="font-mono">VITE_GRAFANA_URL</code> và{' '}
          <code className="font-mono">VITE_PROMETHEUS_URL</code> trong môi trường build của Vercel
          hoặc frontend production.
        </p>
      </div>

      <div>
        <Button onClick={handleSave} className="bg-[#2563A6] text-white font-bold flex items-center gap-2">
          <Save className="w-4 h-4" /> Save Admin Preferences
        </Button>
      </div>
    </div>
  );
};
