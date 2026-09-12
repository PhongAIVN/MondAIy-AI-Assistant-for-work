import {
  completeTask,
  createMeetingNote,
  dismissReminder,
  getDueReminders,
  listConfirmedTasks,
  listProposedTasks,
  recordReminderDeliveries,
  snoozeReminder,
  startTask,
  finalizeRecording,
} from "@/lib/api";
import { applyWebSession, getValidAccessToken } from "@/lib/auth";
import {
  activeReminderBundleItem,
  askedTaskCheckInsItem,
  autoOpenReminderPopupItem,
  notificationBundlesItem,
  pendingTaskCountItem,
} from "@/lib/storage";
import { maybeOpenReminderPopup, shouldAutoOpenReminderPopup } from "@/lib/reminderPopup";
import {
  handleTaskCheckInButton,
  isWithinWorkHours,
  parseTaskCheckInNotificationId,
  selectTaskCheckIn,
} from "@/lib/taskCheckIn";
import {
  IDLE_PROMPT_AFTER_MS,
  decideIdleAction,
  hydrateRecordingSession,
  isActive,
  markChunkFailed,
  markQuotaExhausted,
  markChunkUploaded,
  markDone,
  markEmptyDiscarded,
  markError,
  markIdleAsked,
  markRecording,
  markSignal,
  markStillMeeting,
  recordingSessionNeedsMigration,
  startRequesting,
  stopRecording,
} from "@/lib/recording";
import type { RecordingSession } from "@/lib/recording";
import { RECORDING_MESSAGES, RECORDING_SESSION_KEY } from "@/types";
import type { NotificationBundle, Task } from "@/types";
import type { WebSession } from "@/lib/webSession";

// TODO(OD-06): cadence nhắc việc chưa chốt PM. 15 phút là giá trị tạm an toàn.
const TASK_POLL_ALARM = "mondaiy-task-poll";
const TASK_POLL_PERIOD_MINUTES = 15;
// Ngắn hơn cadence task list vì đây là lời nhắc đến hạn — chờ 15 phút để thấy
// một việc sắp tới hạn là quá trễ so với mốc 30 phút mặc định (FR-090).
const REMINDER_POLL_ALARM = "mondaiy-reminder-poll";
const REMINDER_POLL_PERIOD_MINUTES = 5;
const REMINDER_SNOOZE_MINUTES = 15;
// FR-096 rút gọn cho nút bấm nhanh trên OS notification: không có chỗ chọn 1
// trong 3 lý do ở đây, mặc định lý do trung tính nhất. Chọn lý do đầy đủ vẫn
// làm được từ trang chi tiết task trong web app.
const QUICK_DISMISS_REASON = "khong_can_nua";
const BADGE_COLOR = "#356F83";
// Badge đỏ + chữ REC lúc đang ghi: người dùng phải nhìn thấy ngay là micro đang
// mở, không được để việc thu tiếng diễn ra âm thầm.
const RECORDING_BADGE_COLOR = "#C2453D";
const RECORDING_BADGE_TEXT = "REC";
const OFFSCREEN_URL = "offscreen.html";

// Nhịp kiểm tra khoảng lặng của cuộc họp đang ghi. 1 phút là chu kỳ nhỏ nhất
// chrome.alarms chấp nhận ổn định, và cũng vừa đúng cửa sổ 1 phút chờ trả lời
// nên không cần thêm timer riêng — service worker MV3 bị tắt bất cứ lúc nào,
// setTimeout dài trong đó không sống sót.
const RECORDING_IDLE_ALARM = "mondaiy-recording-idle";
const RECORDING_IDLE_PERIOD_MINUTES = 1;
// Notification hỏi "cuộc họp còn không". Một id cố định để lần hỏi sau thay thế
// lần trước thay vì xếp chồng thông báo.
const RECORDING_IDLE_NOTIFICATION = "mondaiy-recording-idle-check";
let taskCheckInPollInFlight = false;

function tasksPageUrl(): string {
  const webAppUrl = import.meta.env.WXT_WEB_APP_URL;
  if (!webAppUrl) throw new Error("WXT_WEB_APP_URL chưa cấu hình trong .env");
  return `${webAppUrl.replace(/\/$/, "")}/tasks`;
}

/** Trang ghi chú cuộc họp trên web app — mở ngay sau khi dừng ghi. */
function meetingNotePageUrl(noteId: string): string {
  const webAppUrl = import.meta.env.WXT_WEB_APP_URL;
  if (!webAppUrl) throw new Error("WXT_WEB_APP_URL chưa cấu hình trong .env");
  return `${webAppUrl.replace(/\/$/, "")}/meeting-notes/${noteId}`;
}

/** sidePanel.open() cần windowId tường minh (khác chrome.action.openPopup()
 * cũ, tự nhắm cửa sổ đang focus) — dùng cửa sổ được focus gần nhất vì lời gọi
 * này xuất phát từ alarm nền, không có cửa sổ "hiện tại" theo user gesture. */
async function openSidePanelOnFocusedWindow(): Promise<void> {
  const window = await chrome.windows.getLastFocused();
  if (window.id === undefined) throw new Error("Không tìm thấy cửa sổ đang focus.");
  await chrome.sidePanel.open({ windowId: window.id });
}

export default defineBackground(() => {
  // Mở Side Panel khi bấm icon toolbar thay vì popup — panel giữ nguyên khi
  // người dùng đổi qua lại giữa các tab (không đóng theo tab như popup cũ).
  void chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {
    // Chrome cũ hơn không có sidePanel API — không có gì để làm thêm ở đây.
  });

  chrome.alarms.create(TASK_POLL_ALARM, { periodInMinutes: TASK_POLL_PERIOD_MINUTES });
  chrome.alarms.create(REMINDER_POLL_ALARM, { periodInMinutes: REMINDER_POLL_PERIOD_MINUTES });

  chrome.alarms.create(RECORDING_IDLE_ALARM, { periodInMinutes: RECORDING_IDLE_PERIOD_MINUTES });

  chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === TASK_POLL_ALARM) {
      void pollAndNotify();
      void pollTaskCheckIns();
    }
    if (alarm.name === REMINDER_POLL_ALARM) void pollReminders();
    if (alarm.name === RECORDING_IDLE_ALARM) void checkRecordingIdle();
  });

  pendingTaskCountItem.watch((count) => {
    void syncBadge(count);
  });

  chrome.notifications.onButtonClicked.addListener((notificationId, buttonIndex) => {
    if (notificationId === RECORDING_IDLE_NOTIFICATION) {
      void handleIdleAnswer(buttonIndex === 0);
      return;
    }
    void handleTaskCheckInButton(notificationId, buttonIndex, {
      startTask,
      completeTask,
      clearNotification: (id) => {
        void chrome.notifications.clear(id);
      },
    })
      .then((handled) => {
        if (!handled) void handleReminderButton(notificationId, buttonIndex);
      })
      .catch((error: unknown) => {
        // Giữ notification khi API lỗi để người dùng có thể bấm lại; asked-state
        // vẫn giữ nguyên nên alarm không sinh thêm một notification trùng.
        console.warn("Không xử lý được câu trả lời task check-in.", error);
      });
  });

  // Click vào phần thân notification: task-poll mở trang tasks; reminder mở
  // thẳng bằng chứng đã tạo ra việc đó (FR-097) — không có popup gắn sẵn nên
  // phải tự mở tab.
  chrome.notifications.onClicked.addListener((notificationId) => {
    if (notificationId === TASK_POLL_ALARM) {
      void chrome.tabs.create({ url: tasksPageUrl() });
      return;
    }
    // Bấm vào thân thông báo hỏi khoảng lặng: người dùng đang ở máy, hiểu là
    // cuộc họp còn diễn ra. Diễn giải theo hướng giữ bản ghi, vì hiểu nhầm
    // ngược lại sẽ cắt mất phần cuộc họp còn lại.
    if (notificationId === RECORDING_IDLE_NOTIFICATION) {
      void handleIdleAnswer(true);
      return;
    }
    if (parseTaskCheckInNotificationId(notificationId)) {
      void chrome.tabs.create({ url: tasksPageUrl() });
      return;
    }
    void openReminderEvidence(notificationId);
  });

  // content script (web-session.content.ts) báo trạng thái đăng nhập web app
  // mỗi khi trang đó load/đổi tab/thay đổi localStorage — đồng bộ ngay, không
  // đợi tới lần poll định kỳ tiếp theo.
  chrome.runtime.onMessage.addListener((message: { type?: string; session?: WebSession | null }) => {
    if (message?.type !== "mondaiy-web-session") return;
    void applyWebSession(message.session ?? null).then(() => {
      void pollAndNotify();
      void pollTaskCheckIns();
      void pollReminders();
    });
  });

  // Luồng ghi âm cuộc họp: popup ra lệnh bắt đầu/dừng, offscreen báo ngược tiến
  // độ từng chunk. Tách hẳn listener khỏi listener session ở trên cho dễ đọc.
  chrome.runtime.onMessage.addListener(
    (
      message: {
        type?: string;
        tabId?: number;
        message?: string;
        remainingMs?: number | null;
        heard?: boolean;
      },
      _sender: chrome.runtime.MessageSender,
      sendResponse: (response?: unknown) => void
    ) => {
    switch (message?.type) {
      case RECORDING_MESSAGES.requestToken:
        // sendResponse bất đồng bộ nên phải return true để Chrome giữ kênh mở.
        void getValidAccessToken().then(
          (token) => sendResponse({ token }),
          () => sendResponse({ token: null })
        );
        return true;
      case RECORDING_MESSAGES.start:
        if (typeof message.tabId === "number") void handleStartRecording(message.tabId);
        return;
      case RECORDING_MESSAGES.stop:
        void handleStopRecording();
        return;
      case RECORDING_MESSAGES.stillMeeting:
        void handleIdleAnswer(true);
        return;
      case RECORDING_MESSAGES.chunkUploaded: {
        // Chunk nghe ra chữ mới tính là tín hiệu. Chunk chỉ có tiếng ồn vẫn
        // upload thành công nhưng KHÔNG được dời mốc im lặng — nếu không thì
        // phòng họp trống có tiếng quạt cũng giữ máy ghi chạy suốt đêm.
        const heard = message.heard === true;
        void updateRecordingSession((session) => {
          const next = markChunkUploaded(session, message.remainingMs ?? null);
          return heard ? markSignal(next, Date.now()) : next;
        });
        if (heard) chrome.notifications.clear(RECORDING_IDLE_NOTIFICATION);
        return;
      }
      case RECORDING_MESSAGES.chunkFailed:
        void updateRecordingSession((session) => markChunkFailed(session, message.message));
        return;
      case RECORDING_MESSAGES.quotaExhausted:
        // Dừng thu trước rồi mới đánh dấu: handleStopRecording đưa phiên qua
        // finalizing, đánh dấu trước sẽ bị nó ghi đè mất trạng thái hết hạn mức.
        void handleStopRecording().then(() => updateRecordingSession(markQuotaExhausted));
        return;
      case RECORDING_MESSAGES.finished:
        void handleRecordingFinished();
        return;
      case RECORDING_MESSAGES.failed:
        void handleRecordingFailed(message.message ?? "Ghi âm gặp lỗi.");
        return;
      default:
        return;
    }
  });

  void pendingTaskCountItem.getValue().then(syncBadge);
  void pollAndNotify();
  void pollTaskCheckIns();
  void pollReminders();
});

async function syncBadge(count: number): Promise<void> {
  // Đang ghi thì badge REC được ưu tiên — số task chờ vẫn cập nhật trong storage,
  // chỉ tạm không chiếm chỗ hiển thị.
  if (isActive(await readRecordingSession())) return;
  await chrome.action.setBadgeText({ text: count > 0 ? String(count) : "" });
  await chrome.action.setBadgeBackgroundColor({ color: BADGE_COLOR });
}

async function pollAndNotify(): Promise<void> {
  let count: number;
  try {
    count = (await listProposedTasks()).length;
  } catch {
    // Chưa đăng nhập hoặc lỗi mạng — im lặng, không báo sai số liệu.
    return;
  }

  await pendingTaskCountItem.setValue(count);
  if (count <= 0) return;

  chrome.notifications.create(TASK_POLL_ALARM, {
    type: "basic",
    iconUrl: "/loadinggif1.gif",
    title: "mondaiy",
    message: `Bạn có ${count} việc cần xử lý.`,
    priority: 1,
  });
}

async function pollTaskCheckIns(): Promise<void> {
  if (taskCheckInPollInFlight) return;
  taskCheckInPollInFlight = true;
  try {
    const now = new Date();
    // Check trước network để 22:00–08:00 không đánh thức API chỉ để rồi bỏ kết quả.
    if (!isWithinWorkHours(now)) return;

    let tasks: Task[];
    let askedByNotificationId: Record<string, true>;
    try {
      [tasks, askedByNotificationId] = await Promise.all([
        listConfirmedTasks(),
        askedTaskCheckInsItem.getValue(),
      ]);
    } catch (error) {
      console.warn("Không đọc được dữ liệu task check-in.", error);
      return;
    }

    const prompt = selectTaskCheckIn(tasks, askedByNotificationId, now);
    if (!prompt) return;

    // Persist trước khi gọi Chrome: service worker có thể bị dừng ngay sau khi
    // notification hiện; ghi sau sẽ khiến lượt alarm kế tiếp hỏi trùng.
    try {
      await askedTaskCheckInsItem.setValue({
        ...askedByNotificationId,
        [prompt.notificationId]: true,
      });
    } catch (error) {
      console.warn("Không lưu được trạng thái task check-in; không hiện notification.", error);
      return;
    }

    try {
      await chrome.notifications.create(prompt.notificationId, {
        type: "basic",
        iconUrl: "/loadinggif1.gif",
        title: prompt.title,
        message: prompt.message,
        priority: 1,
        buttons: prompt.buttons,
      });
    } catch (error) {
      // Không rollback asked-state: invariant không hỏi lặp quan trọng hơn retry
      // một notification mà Chrome đã từ chối tạo trong trạng thái không rõ.
      console.warn("Không tạo được task check-in notification.", error);
    }
  } finally {
    taskCheckInPollInFlight = false;
  }
}

function bundleMessage(bundle: NotificationBundle): string {
  const first = bundle.tasks[0];
  if (!first) return "";
  const otherCount = bundle.tasks.length - 1;
  return otherCount === 0 ? first.title : `${first.title} và ${otherCount} việc khác`;
}

async function pollReminders(): Promise<void> {
  let bundles: NotificationBundle[];
  try {
    bundles = await getDueReminders();
  } catch {
    // Chưa đăng nhập hoặc lỗi mạng — lặng lẽ đợi lượt poll sau, không tự chế
    // dữ liệu nhắc việc khi chưa chắc chắn.
    return;
  }
  if (bundles.length === 0) return;
  const firstBundle = bundles[0];
  if (!firstBundle) return;

  const stored = await notificationBundlesItem.getValue();
  const next = { ...stored };

  for (const bundle of bundles) {
    const notificationId = `mondaiy-reminder-${bundle.bundleKey}`;
    chrome.notifications.create(notificationId, {
      type: "basic",
      iconUrl: "/loadinggif1.gif",
      title: "mondaiy nhắc việc",
      message: bundleMessage(bundle),
      priority: 1,
      buttons: [{ title: `Nhắc lại ${REMINDER_SNOOZE_MINUTES}p` }, { title: "Bỏ qua" }],
    });
    next[notificationId] = bundle;

    try {
      await recordReminderDeliveries(bundle.reminderIds);
    } catch {
      // Không throw: OS notification đã hiện. Nếu request này thật sự chưa
      // tới server, /reminders/due lần poll sau sẽ trả lại đúng bundle này —
      // idempotent theo thiết kế (FR-091), không mất, chỉ lặp hiển thị.
    }
  }

  await notificationBundlesItem.setValue(next);
  const autoOpen = await autoOpenReminderPopupItem.getValue();
  if (!autoOpen) return;

  // pollReminders() chạy lại mỗi lần web app báo đổi phiên đăng nhập (không
  // chỉ mỗi 5 phút từ alarm) — bundle còn hạn thì server vẫn trả y hệt, nên
  // không có guard này thì mỗi lần đăng nhập/đổi tab web app sẽ ép mở lại
  // popup cho đúng 1 bundle user vừa tự đóng.
  const activeBundle = await activeReminderBundleItem.getValue();
  if (!shouldAutoOpenReminderPopup(firstBundle, activeBundle)) return;

  // Ghi ngữ cảnh trước khi mở: popup mount rất nhanh và phải đọc được
  // đúng reminder ngay từ frame đầu. Chỉ mở một lần cho cả batch.
  await activeReminderBundleItem.setValue(firstBundle);
  const openPopup =
    typeof chrome.sidePanel?.open === "function" ? () => openSidePanelOnFocusedWindow() : undefined;
  const result = await maybeOpenReminderPopup(autoOpen, openPopup);
  if (result !== "opened") await activeReminderBundleItem.setValue(null);
}

async function handleReminderButton(notificationId: string, buttonIndex: number): Promise<void> {
  const stored = await notificationBundlesItem.getValue();
  const bundle = stored[notificationId];
  if (!bundle) return;

  try {
    if (buttonIndex === 0) {
      await Promise.all(bundle.reminderIds.map((id) => snoozeReminder(id, REMINDER_SNOOZE_MINUTES)));
    } else {
      await Promise.all(bundle.reminderIds.map((id) => dismissReminder(id, QUICK_DISMISS_REASON)));
    }
  } catch {
    // Lỗi mạng giữa chừng — không xoá khỏi storage bên dưới nếu request hỏng
    // thật sự thất bại thì user có thể mở trang tasks để xử lý lại, dữ liệu
    // trên server vẫn ở trạng thái cũ (không mất, không đổi sai).
    return;
  }

  chrome.notifications.clear(notificationId);
  const next = { ...stored };
  delete next[notificationId];
  await notificationBundlesItem.setValue(next);
  await clearActiveReminder(bundle.bundleKey);
}

/** Đọc phiên ghi đang lưu; chưa có gì thì trả phiên rỗng thay vì undefined. */
async function readRecordingSession(): Promise<RecordingSession> {
  const stored = await chrome.storage.local.get(RECORDING_SESSION_KEY);
  const rawSession = stored[RECORDING_SESSION_KEY];
  const session = hydrateRecordingSession(rawSession);

  // Ghi schema mới đúng một lần. Nếu chỉ hydrate trong bộ nhớ, popup mở trước
  // lần update kế tiếp vẫn có thể đọc object cũ và hiểu `undefined !== null`
  // thành đang treo câu hỏi khoảng lặng.
  if (recordingSessionNeedsMigration(rawSession)) {
    await chrome.storage.local.set({ [RECORDING_SESSION_KEY]: session });
  }
  return session;
}

/**
 * Ghi phiên xuống storage rồi đồng bộ badge. Popup không hỏi background mà nghe
 * thẳng chrome.storage.onChanged, nên mọi thay đổi phải đi qua đây.
 */
async function writeRecordingSession(session: RecordingSession): Promise<void> {
  await chrome.storage.local.set({ [RECORDING_SESSION_KEY]: session });
  await syncRecordingBadge(session);
}

/** Đọc–biến đổi–ghi trong một nhịp, tránh lặp lại ba dòng ở mọi handler. */
async function updateRecordingSession(
  transform: (session: RecordingSession) => RecordingSession
): Promise<void> {
  await writeRecordingSession(transform(await readRecordingSession()));
}

/** Đang ghi thì badge đỏ; ghi xong thì trả badge về đúng số task đang chờ. */
async function syncRecordingBadge(session: RecordingSession): Promise<void> {
  if (isActive(session)) {
    await chrome.action.setBadgeText({ text: RECORDING_BADGE_TEXT });
    await chrome.action.setBadgeBackgroundColor({ color: RECORDING_BADGE_COLOR });
    return;
  }
  const count = await pendingTaskCountItem.getValue();
  await chrome.action.setBadgeText({ text: count > 0 ? String(count) : "" });
  await chrome.action.setBadgeBackgroundColor({ color: BADGE_COLOR });
}

/**
 * Chrome chỉ cho phép một offscreen document tại một thời điểm — tạo lần hai sẽ
 * ném lỗi. Kiểm tra trước, và vẫn bọc try/catch phòng trường hợp hai lệnh tạo
 * chạy sát nhau.
 */
async function ensureOffscreenDocument(): Promise<void> {
  if (await chrome.offscreen.hasDocument()) return;
  try {
    await chrome.offscreen.createDocument({
      url: OFFSCREEN_URL,
      reasons: ["USER_MEDIA"],
      justification: "Ghi âm cuộc họp để tạo ghi chú",
    });
  } catch (error) {
    if (!(await chrome.offscreen.hasDocument())) throw error;
  }
}

/** Đóng offscreen để giải phóng micro; không có document sẵn thì bỏ qua. */
async function closeOffscreenDocument(): Promise<void> {
  if (!(await chrome.offscreen.hasDocument())) return;
  await chrome.offscreen.closeDocument();
}

function recordingStartErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  if (/permission dismissed|notallowed|user.?denied|user.?gesture/i.test(message)) {
    return "Chrome chưa cho phép lấy âm thanh tab. Hãy bấm lại nút Ghi cuộc họp trực tiếp trong Side Panel và cho phép quyền nếu Chrome hỏi.";
  }
  return message || "Không bắt đầu ghi được.";
}

/**
 * Bắt đầu ghi: lấy streamId ngay từ cú bấm trước, rồi mới tạo note để có id
 * cho từng chunk và bàn giao cho offscreen vì service worker không có DOM.
 */
async function handleStartRecording(tabId: number): Promise<void> {
  // tabCapture phải được gọi ngay khi nhận message từ cú bấm của người dùng.
  // Mọi await trước lời gọi này (storage/API) làm Chrome mất user gesture và
  // trả lỗi "Permission dismissed" dù quyền extension đã khai báo đúng.
  let streamId: string;
  try {
    streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tabId });
  } catch (error) {
    await updateRecordingSession((session) => markError(session, recordingStartErrorMessage(error)));
    return;
  }

  await updateRecordingSession(startRequesting);
  try {
    const note = await createMeetingNote();
    await ensureOffscreenDocument();

    const startedAt = Date.now();
    await chrome.runtime.sendMessage({
      type: RECORDING_MESSAGES.offscreenStart,
      streamId,
      noteId: note.id,
      startedAt,
    });
    await updateRecordingSession((session) => markRecording(session, note.id, startedAt));
  } catch (error) {
    await closeOffscreenDocument();
    await updateRecordingSession((session) =>
      markError(session, recordingStartErrorMessage(error))
    );
  }
}

/** Dừng theo yêu cầu người dùng; bấm lúc không ghi thì im lặng bỏ qua. */
async function handleStopRecording(): Promise<void> {
  const session = await readRecordingSession();
  if (!isActive(session)) return;
  // Câu hỏi khoảng lặng có thể còn treo trên màn hình: phiên đã dừng rồi thì
  // bấm trả lời không còn nghĩa gì nữa.
  chrome.notifications.clear(RECORDING_IDLE_NOTIFICATION);
  await writeRecordingSession(stopRecording(session));
  await chrome.runtime.sendMessage({ type: RECORDING_MESSAGES.offscreenStop }).catch(() => {
    // Offscreen đã chết trước khi kịp nhận lệnh — vẫn phải khép phiên lại.
    void handleRecordingFinished();
  });
}

/**
 * Offscreen báo đã upload nốt chunk cuối: đóng offscreen, nhờ server khép sổ rồi
 * mới quyết định có mở trang ghi chú hay không.
 *
 * Server xoá luôn cuộc họp không thu được chữ nào (mic tắt, bấm nhầm, họp chưa
 * bắt đầu), nên mở trang trong trường hợp đó sẽ ra 404. Finalize lỗi thì vẫn mở
 * trang: nội dung đã ghi vẫn nằm trong DB, chỉ là chưa được đặt tên.
 */
async function handleRecordingFinished(): Promise<void> {
  const session = await readRecordingSession();
  await closeOffscreenDocument();

  let deleted = false;
  let title: string | undefined;
  if (session.noteId) {
    try {
      const result = await finalizeRecording(session.noteId);
      deleted = result.deleted;
      title = result.title;
    } catch {
      // Mất mạng đúng lúc dừng — không có gì cứu được ở đây, cứ mở trang ghi chú.
    }
  }

  await writeRecordingSession(deleted ? markEmptyDiscarded(session) : markDone(session, title));
  if (session.noteId && !deleted) {
    await chrome.tabs.create({ url: meetingNotePageUrl(session.noteId) });
  }
}

/**
 * Kiểm tra khoảng lặng mỗi phút và xử lý theo đúng một trong ba nước đi.
 *
 * Cơ chế: mốc tín hiệu cuối được dời mỗi khi server nghe ra chữ. Im lặng quá
 * IDLE_PROMPT_AFTER_MS thì hiện thông báo hỏi cuộc họp còn diễn ra không; không
 * ai trả lời trong IDLE_AUTO_STOP_AFTER_MS thì tự dừng. Toàn bộ quyết định nằm
 * ở `decideIdleAction` (hàm thuần, test được), ở đây chỉ còn phần chạm chrome.*.
 *
 * Dừng tự động đi qua đúng `handleStopRecording` như người dùng bấm dừng: chunk
 * cuối vẫn được tải lên, cuộc họp vẫn được đặt tên, không mất phần đã ghi.
 */
async function checkRecordingIdle(): Promise<void> {
  const session = await readRecordingSession();
  const now = Date.now();
  switch (decideIdleAction(session, now)) {
    case "ask":
      chrome.notifications.create(RECORDING_IDLE_NOTIFICATION, {
        type: "basic",
        iconUrl: "/icon/128.png",
        title: "mondaiy vẫn đang ghi",
        message:
          `Không nghe thấy gì trong ${Math.round(IDLE_PROMPT_AFTER_MS / 60_000)} phút. ` +
          "Cuộc họp còn diễn ra không? Không trả lời trong 1 phút thì mình dừng ghi.",
        priority: 2,
        requireInteraction: true,
        buttons: [{ title: "Vẫn đang họp" }, { title: "Dừng ghi" }],
      });
      await updateRecordingSession((current) => markIdleAsked(current, now));
      return;
    case "stop":
      chrome.notifications.clear(RECORDING_IDLE_NOTIFICATION);
      await handleStopRecording();
      return;
    default:
      return;
  }
}

/** Trả lời câu hỏi khoảng lặng: ghi tiếp và dời mốc, hoặc dừng luôn. */
async function handleIdleAnswer(stillMeeting: boolean): Promise<void> {
  chrome.notifications.clear(RECORDING_IDLE_NOTIFICATION);
  if (!stillMeeting) {
    await handleStopRecording();
    return;
  }
  await updateRecordingSession((session) => markStillMeeting(session, Date.now()));
}

/** Lỗi chặn cả phiên (từ chối micro, tab đóng giữa chừng...) — dọn offscreen rồi báo popup. */
async function handleRecordingFailed(message: string): Promise<void> {
  await closeOffscreenDocument();
  await updateRecordingSession((session) => markError(session, message));
}

async function openReminderEvidence(notificationId: string): Promise<void> {
  const stored = await notificationBundlesItem.getValue();
  const bundle = stored[notificationId];
  const url = bundle?.tasks[0]?.evidenceDeepLink ?? tasksPageUrl();
  await chrome.tabs.create({ url });
  chrome.notifications.clear(notificationId);
  if (bundle) await clearActiveReminder(bundle.bundleKey);
}

async function clearActiveReminder(bundleKey: string): Promise<void> {
  const active = await activeReminderBundleItem.getValue();
  if (active?.bundleKey === bundleKey) await activeReminderBundleItem.setValue(null);
}
