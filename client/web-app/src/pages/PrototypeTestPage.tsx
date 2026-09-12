import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore, type BriefingSimulatedState } from '../stores/useAppStore';
import { usePreferencesStore } from '../stores/usePreferencesStore';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import {
  SlidersHorizontal,
  RotateCcw,
  FileText,
  Download,
  ExternalLink,
  User,
  FlaskConical
} from 'lucide-react';

export const PrototypeTestPage: React.FC = () => {
  const navigate = useNavigate();
  const { briefingState, setBriefingState, addToast } = useAppStore();
  const { resetAllPrototypeData } = usePreferencesStore();

  const [participantId, setParticipantId] = useState('P-101');
  
  const [taskState, setTaskState] = useState([
    {
      id: 1,
      title: 'Test Task 1 — Find what is new in today’s briefing',
      instruction: 'Navigate to the Daily Briefing page. Locate the "Changes Since Last Briefing" section and identify what extended or updated today.',
      status: 'not_started' as 'not_started' | 'in_progress' | 'passed' | 'failed',
      severity: 'none' as 'none' | 'low' | 'medium' | 'high' | 'critical',
      notes: '',
    },
    {
      id: 2,
      title: 'Test Task 2 — Explain why an urgent deadline is relevant',
      instruction: 'Switch scenario to "Urgent Deadline". Locate the urgent item and explain why the deliverable matters to your milestone evaluation.',
      status: 'not_started' as 'not_started' | 'in_progress' | 'passed' | 'failed',
      severity: 'none' as 'none' | 'low' | 'medium' | 'high' | 'critical',
      notes: '',
    },
    {
      id: 3,
      title: 'Test Task 3 — Open source evidence for a briefing item',
      instruction: 'Click on the source platform badge (e.g. Discord or Canvas LMS) on any briefing card to view the exact location, raw quote, and timestamp.',
      status: 'not_started' as 'not_started' | 'in_progress' | 'passed' | 'failed',
      severity: 'none' as 'none' | 'low' | 'medium' | 'high' | 'critical',
      notes: '',
    },
    {
      id: 4,
      title: 'Test Task 4 — Resolve a conflict without silent system choice',
      instruction: 'Switch scenario to "Source Conflict". Compare the conflicting Discord vs Canvas deadlines and draft a mentor question without accepting an auto-chosen winner.',
      status: 'not_started' as 'not_started' | 'in_progress' | 'passed' | 'failed',
      severity: 'none' as 'none' | 'low' | 'medium' | 'high' | 'critical',
      notes: '',
    },
    {
      id: 5,
      title: 'Test Task 5 — Review a calendar suggestion without auto-creation',
      instruction: 'Navigate to Program Calendar or click "Review schedule" from Briefing. Verify that a review modal appears before any calendar event is added.',
      status: 'not_started' as 'not_started' | 'in_progress' | 'passed' | 'failed',
      severity: 'none' as 'none' | 'low' | 'medium' | 'high' | 'critical',
      notes: '',
    },
  ]);

  const updateTask = (id: number, key: string, val: any) => {
    setTaskState((prev) =>
      prev.map((t) => (t.id === id ? { ...t, [key]: val } : t))
    );
  };

  const handleResetData = () => {
    if (window.confirm('Reset prototype state, notifications, tasks, and test data?')) {
      resetAllPrototypeData();
      addToast({
        type: 'info',
        title: 'Prototype Data Restored',
        message: 'Prototype data and scenario states restored to defaults.',
      });
    }
  };

  const handleExportResults = () => {
    const report = {
      participantId,
      currentBriefingScenario: briefingState,
      timestamp: new Date().toISOString(),
      tasks: taskState,
    };

    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(report, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `usability_test_${participantId}_${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();

    addToast({
      type: 'success',
      title: 'Test Report Exported',
      message: `Exported usability results for participant ${participantId}.`,
    });
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-[#D5DDEB] shadow-xs">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-[#2563A6] mb-1">
            <FlaskConical className="w-4 h-4" /> Research Protocol
          </div>
          <h1 className="text-3xl font-semibold text-[#0F1F38] font-heading">
            Usability Testing Support Console
          </h1>
          <p className="text-xs text-[#5A6A85] mt-1">
            Moderator test runner for prototype evaluation, task status tracking, and severity logging.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            icon={<RotateCcw className="w-3.5 h-3.5 text-[#A03D3D]" />}
            onClick={handleResetData}
          >
            Reset Data
          </Button>
          <Button
            variant="primary"
            size="sm"
            icon={<Download className="w-3.5 h-3.5 text-[#E1EBFA]" />}
            onClick={handleExportResults}
          >
            Export JSON
          </Button>
        </div>
      </div>

      {/* Participant ID & Testing Mode Selector */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-4 space-y-2">
          <label className="block text-xs font-bold text-[#0F1F38] flex items-center gap-1.5">
            <User className="w-4 h-4 text-[#2563A6]" /> Participant ID
          </label>
          <input
            type="text"
            value={participantId}
            onChange={(e) => setParticipantId(e.target.value)}
            className="w-full p-2.5 bg-[#EDF2FB] border border-[#D5DDEB] rounded-xl text-xs font-bold text-[#0F1F38]"
            placeholder="e.g. P-101"
          />
        </Card>

        <Card className="p-4 space-y-2">
          <label className="block text-xs font-bold text-[#0F1F38] flex items-center gap-1.5">
            <SlidersHorizontal className="w-4 h-4 text-[#2563A6]" /> Active Scenario (Testing Mode)
          </label>
          <div className="flex items-center gap-1.5 flex-wrap">
            {(['normal', 'urgent', 'conflict', 'no_updates', 'limited_coverage'] as BriefingSimulatedState[]).map(
              (st) => (
                <button
                  key={st}
                  onClick={() => setBriefingState(st)}
                  className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all capitalize ${
                    briefingState === st
                      ? 'bg-[#0F1F38] text-white shadow-xs'
                      : 'bg-[#EDF2FB] text-[#5A6A85] hover:bg-[#EBEFF8] border border-[#D5DDEB]'
                  }`}
                >
                  {st.replace('_', ' ')}
                </button>
              )
            )}
          </div>
        </Card>
      </div>

      {/* Usability Tasks List */}
      <div className="space-y-4">
        <h2 className="text-base font-extrabold text-[#0F1F38] font-heading flex items-center gap-2">
          <FileText className="w-4 h-4 text-[#2563A6]" /> Test Tasks (1 - 5)
        </h2>

        {taskState.map((task) => (
          <Card key={task.id} className="p-5 space-y-4 border-l-4 border-l-[#2563A6]">
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
              <div className="space-y-1 max-w-2xl">
                <h3 className="text-sm font-extrabold text-[#0F1F38] font-heading">{task.title}</h3>
                <p className="text-xs text-[#5A6A85] leading-relaxed">{task.instruction}</p>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <Button
                  variant="outline"
                  size="xs"
                  onClick={() => navigate('/briefing')}
                  icon={<ExternalLink className="w-3 h-3" />}
                >
                  Jump to Briefing
                </Button>
              </div>
            </div>

            {/* Task Moderator Controls */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-3 border-t border-[#D5DDEB] text-xs">
              <div>
                <label className="block font-bold text-[#0F1F38] mb-1">Completion Status</label>
                <select
                  value={task.status}
                  onChange={(e) => updateTask(task.id, 'status', e.target.value)}
                  className="w-full p-2 bg-[#EDF2FB] border border-[#D5DDEB] rounded-lg font-semibold"
                >
                  <option value="not_started">⚪ Not Started</option>
                  <option value="in_progress">🟡 In Progress</option>
                  <option value="passed">🟢 Passed</option>
                  <option value="failed">🔴 Failed</option>
                </select>
              </div>

              <div>
                <label className="block font-bold text-[#0F1F38] mb-1">Issue Severity</label>
                <select
                  value={task.severity}
                  onChange={(e) => updateTask(task.id, 'severity', e.target.value)}
                  className="w-full p-2 bg-[#EDF2FB] border border-[#D5DDEB] rounded-lg font-semibold"
                >
                  <option value="none">None</option>
                  <option value="low">Low (Minor friction)</option>
                  <option value="medium">Medium (Hesitation / Delay)</option>
                  <option value="high">High (Significant confusion)</option>
                  <option value="critical">Critical (Blocking issue)</option>
                </select>
              </div>

              <div className="sm:col-span-2">
                <label className="block font-bold text-[#0F1F38] mb-1">Observer Notes</label>
                <textarea
                  rows={2}
                  value={task.notes}
                  onChange={(e) => updateTask(task.id, 'notes', e.target.value)}
                  placeholder="Record participant verbalizations, time-on-task, or confusion points..."
                  className="w-full p-2 bg-[#EDF2FB] border border-[#D5DDEB] rounded-lg text-xs"
                />
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
};
