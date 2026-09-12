import type { Task } from "@/types";

export type TaskCheckInQuestion = "start" | "complete";

export interface TaskCheckInPrompt {
  taskId: number;
  question: TaskCheckInQuestion;
  notificationId: string;
  title: string;
  message: string;
  buttons: [{ title: string }, { title: string }];
}

export interface TaskCheckInActions {
  startTask(taskId: number): Promise<unknown>;
  completeTask(taskId: number): Promise<unknown>;
  clearNotification(notificationId: string): void;
}

const TASK_CHECK_IN_PREFIX = "mondaiy-task-check-in";
const WORKDAY_START_MINUTES = 8 * 60;
const WORKDAY_END_MINUTES = 22 * 60;

// Đồng bộ với NEUTRAL_JOB_SIZE_MIN của planner. TaskResponse chưa expose khoảng
// estimate; production hiện cũng chưa có mẫu actual_minutes để cá nhân hoá.
export const NEUTRAL_ESTIMATE_MINUTES = 30;

export function isWithinWorkHours(now: Date): boolean {
  const localMinutes = now.getHours() * 60 + now.getMinutes();
  return localMinutes >= WORKDAY_START_MINUTES && localMinutes < WORKDAY_END_MINUTES;
}

export function taskCheckInNotificationId(
  taskId: number,
  question: TaskCheckInQuestion
): string {
  return `${TASK_CHECK_IN_PREFIX}-${question}-${taskId}`;
}

export function parseTaskCheckInNotificationId(
  notificationId: string
): { taskId: number; question: TaskCheckInQuestion } | null {
  const match = notificationId.match(/^mondaiy-task-check-in-(start|complete)-(\d+)$/);
  if (!match) return null;
  const question = match[1];
  const taskId = Number(match[2]);
  if ((question !== "start" && question !== "complete") || !Number.isSafeInteger(taskId)) {
    return null;
  }
  return { taskId, question };
}

function promptFor(task: Task, question: TaskCheckInQuestion): TaskCheckInPrompt {
  const starting = question === "start";
  return {
    taskId: task.id,
    question,
    notificationId: taskCheckInNotificationId(task.id, question),
    title: starting ? "Bắt đầu làm việc này chưa?" : "Xong chưa?",
    message: task.title,
    buttons: starting
      ? [{ title: "Đang làm" }, { title: "Chưa" }]
      : [{ title: "Xong" }, { title: "Chưa xong" }],
  };
}

export function selectTaskCheckIn(
  tasks: Task[],
  askedByNotificationId: Record<string, true>,
  now: Date
): TaskCheckInPrompt | null {
  if (!isWithinWorkHours(now)) return null;

  for (const task of tasks) {
    if (task.status !== "confirmed") continue;

    if (!task.startedAt) {
      const prompt = promptFor(task, "start");
      if (!askedByNotificationId[prompt.notificationId]) return prompt;
      continue;
    }

    const startedAtMs = Date.parse(task.startedAt);
    if (!Number.isFinite(startedAtMs)) continue;
    const elapsedMinutes = (now.getTime() - startedAtMs) / 60_000;
    if (elapsedMinutes < NEUTRAL_ESTIMATE_MINUTES) continue;

    const prompt = promptFor(task, "complete");
    if (!askedByNotificationId[prompt.notificationId]) return prompt;
  }

  return null;
}

export async function handleTaskCheckInButton(
  notificationId: string,
  buttonIndex: number,
  actions: TaskCheckInActions
): Promise<boolean> {
  const prompt = parseTaskCheckInNotificationId(notificationId);
  if (!prompt) return false;

  if (buttonIndex !== 0) {
    actions.clearNotification(notificationId);
    return true;
  }

  if (prompt.question === "start") {
    await actions.startTask(prompt.taskId);
  } else {
    await actions.completeTask(prompt.taskId);
  }
  actions.clearNotification(notificationId);
  return true;
}
