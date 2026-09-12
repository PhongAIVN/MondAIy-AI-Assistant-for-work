import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

test('app entry loads fonts without invoking a hook during boot', async () => {
  const source = await readFile('App.tsx', 'utf8');

  assert.match(source, /Font\.loadAsync/);
  assert.doesNotMatch(source, /useFonts/);
  assert.match(source, /SafeAreaProvider/);
});

test('workspace does not invoke hooks at module scope', async () => {
  const source = await readFile('src/components/RealWorkspace.tsx', 'utf8');
  const beforeFirstComponent = source.slice(0, source.indexOf('export function RealWorkspace'));
  const betweenComponents = source.slice(source.indexOf('export function RealWorkspace'), source.indexOf('export function RealWorkspace') + 5000);

  assert.doesNotMatch(beforeFirstComponent, /use(?:State|Effect|Memo|Callback|Ref)\(/);
  assert.match(betweenComponents, /function RealWorkspace[\s\S]*useState\(/);
});

test('mobile workspace keeps connected-source, history, meeting-notes and keyboard-safe chat flows', async () => {
  const source = await readFile('src/components/WorkspaceMobileViews.tsx', 'utf8');

  assert.match(source, /id: 'slack'/);
  assert.match(source, /onConversationSelect\(conversation\.id\)/);
  assert.match(source, /MeetingNotes/);
  assert.match(source, /KeyboardAvoidingView/);
  assert.match(source, /Keyboard\.dismiss/);
  assert.match(source, /onPress=\{dismissKeyboard\}/);
  assert.match(source, /keyboardDismissMode="interactive"/);
  assert.match(source, /marginBottom: inputFocused \? 64 : 8/);
  assert.match(source, /chatDismissLayer/);
  assert.match(source, /maxHeight: 150/);
  assert.match(source, /RenderHTML/);
  assert.match(source, /formatAssistantMarkup/);
  assert.match(source, /Ask MondAIy/);
  assert.match(source, /TraceActivity/);
  assert.match(source, /MessageFeedback/);
  assert.match(source, /rateConversationMessage/);
  assert.match(source, /thumbs-up-outline/);
  assert.match(source, /keyboardShouldPersistTaps="handled"/);
  assert.match(source, /keyboardDismissMode="interactive"/);
  assert.match(source, /insets\.bottom/);
  assert.match(source, /keyboardVerticalOffset=\{0\}/);
  assert.doesNotMatch(source, /DESIGN SPEC|SafeAreaInsets\.bottom/);
  assert.doesNotMatch(source, /LITTLEBIRD|Littlebird/);
  assert.match(source, /Animated\.timing\(promptOffset/);
  assert.match(source, /require\('\.\.\/\.\.\/assets\/monbthvippro \(1\)\.png'\)/);
  assert.match(source, /chatMascotOriginal/);
  assert.match(source, /chatPrompts/);
  assert.match(source, /initialBriefing/);
  assert.match(source, /setRecording\(true\)/);
  assert.match(source, /showAiConsent/);
  assert.match(source, /Chia sẻ dữ liệu với AI/);
  assert.match(source, /OpenRouter, Groq hoặc OpenAI/);
  assert.match(source, /Không đồng ý/);
  assert.match(source, /Đồng ý & tiếp tục/);
  assert.match(source, /onAiDataSharingChange/);
  assert.match(source, /voiceScreen/);
  assert.match(source, /ExpoSpeechRecognitionModule/);
  assert.match(source, /expo-image-picker/);
  assert.match(source, /requestMediaLibraryPermissionsAsync/);
  assert.match(source, /selectedImage/);
  assert.match(source, /sendConversationTurn\(\{ conversationId: activeConversationId/);
  assert.doesNotMatch(source, /onConversationCreated\(currentId\)/);
  assert.match(source, /executionEnvironment === 'storeClient'/);
  assert.match(source, /vi-VN/);
  assert.match(source, /interimResults: true/);
  assert.match(source, /MondAIy có thể sai/);

  const workspace = await readFile('src/components/RealWorkspace.tsx', 'utf8');
  assert.match(workspace, /const REDIRECT = MOBILE_GOOGLE_CALLBACK_URI/);
  assert.match(workspace, /accessibilityRole="tab"/);
  assert.match(workspace, /height: 74/);
  assert.match(workspace, /minute/);
  assert.match(workspace, /onOpenBriefing/);
  assert.match(workspace, /setBriefingPreview\(null\); setActiveConversationId\(id\)/);
  assert.doesNotMatch(workspace, /key=\{`\$\{chatNonce\}-\$\{activeConversationId/);
  assert.match(workspace, /listConversations\(token\)\.then/);
  assert.match(workspace, /AppState\.addEventListener/);
  assert.match(workspace, /findBriefingRoutine\(body\.routines\)/);
  assert.match(workspace, /KeyboardAvoidingView/);
  assert.match(workspace, /keyboardVisible/);
  assert.match(workspace, /!keyboardVisible \? <Nav/);
  assert.match(workspace, /intervalDays/);
  assert.match(workspace, /Cách mỗi bao nhiêu ngày/);
  assert.match(workspace, /Chọn thứ chạy hàng tuần/);

  const client = await readFile('src/api/client.ts', 'utf8');
  assert.match(client, /auth\/refresh/);
  assert.match(client, /deleteConversation/);
  assert.match(client, /completeTask/);
  assert.match(client, /createCalendarEvent/);
  assert.match(client, /snoozeReminder/);
    assert.match(client, /getMeetingNote/);
    assert.match(client, /createMeetingNote/);
    assert.match(client, /updateMeetingNote/);
    assert.match(client, /endMeetingNote/);
    assert.match(source, /MeetingNoteEditor/);
    assert.match(source, /Tổng hợp bằng Mondaiy/);
    assert.match(source, /acceptMeetingActionItem/);
  assert.match(client, /listIntegrationSources/);
  assert.match(client, /deleteAccount/);
});

test('premium authentication screens keep all auth states and real provider flows', async () => {
  const source = await readFile('src/components/AuthScreens.tsx', 'utf8');

  assert.match(source, /export function AuthLayout/);
  assert.match(source, /export function Input/);
  assert.match(source, /export function PrimaryButton/);
  assert.match(source, /export function SocialButton/);
  assert.match(source, /export function AuthFooter/);
  assert.match(source, /type AuthMode = 'login' \| 'register' \| 'forgot'/);
  assert.match(source, /Quên mật khẩu\?/);
  assert.match(source, /forgotPassword\(email\.trim\(\)\)/);
  assert.match(source, /exchangeGoogleLoginCode/);
  assert.match(source, /exchangeAppleIdentityToken/);
  assert.match(source, /monbthvippro \(1\)\.png/);
  assert.match(source, /#FFFFDE/);
  assert.match(source, /#171717/);
  assert.doesNotMatch(source, /Câu hỏi và ảnh có thể được xử lý bởi OpenRouter/);
});

test('lock-screen widget preview is configurable and uses live calendar and task data', async () => {
  const source = await readFile('src/components/LockScreenWidgetPreview.tsx', 'utf8');

  assert.match(source, /listCalendarEvents/);
  assert.match(source, /tasks: Task\[\]/);
  assert.match(source, /type WidgetSection = 'week' \| 'schedule' \| 'tasks'/);
  assert.match(source, /function Tasks/);
  assert.doesNotMatch(source, /NotificationEntry|function Reminders/);
  assert.match(source, /accessibilityRole="switch"/);
  assert.match(source, /Widget Extension/);
});

test('new-user onboarding has four steps, website handoff and mascot setup loading', async () => {
  const source = await readFile('src/components/MobileProduct.tsx', 'utf8');

  assert.match(source, /onboardingPage < 3/);
  assert.match(source, /\[0, 1, 2, 3\]/);
  assert.match(source, /https:\/\/mondaiy\.io\.vn/);
  assert.match(source, /function SetupLoading/);
  assert.match(source, /Animated\.loop/);
  assert.match(source, /ApiConnectionError/);
  assert.match(source, /function SetupFailure/);
  assert.match(source, /Chưa thể mở không gian/);
  assert.match(source, /setBootAttempt/);
});

test('iOS Lock Screen extension keeps the app bundle and uses its own widget bundle', async () => {
  const config = await readFile('app.json', 'utf8');
  const widget = await readFile('src/widgets/MondaiyLockScreenWidget.tsx', 'utf8');

  assert.match(config, /"bundleIdentifier": "com\.mondaiy\.product"/);
  assert.match(config, /"bundleIdentifier": "com\.mondaiy\.product\.widgets"/);
  assert.match(config, /"groupIdentifier": "group\.com\.mondaiy\.product"/);
  assert.match(config, /"expo-background-task"/);
  assert.match(config, /"expo-share-intent"/);
  assert.match(config, /"iosShareExtensionBundleIdentifier": "com\.mondaiy\.product\.share"/);
  assert.match(config, /"NSExtensionActivationSupportsFileWithMaxCount": 5/);
  assert.match(config, /"accessoryRectangular"/);
  assert.match(config, /"systemMedium"/);
  assert.match(config, /"systemLarge"/);
  assert.match(widget, /createWidget<LockScreenWidgetData>\('MondaiyLockScreen'/);
  assert.match(widget, /LỊCH & VIỆC CỦA BẠN/);
  assert.match(widget, /VIỆC CẦN LÀM/);
  assert.match(widget, /tasks: WidgetTask\[\]/);
  assert.doesNotMatch(widget, /habit|weather|reminderCount|reminders/i);
  assert.match(widget, /environment\.widgetFamily === 'systemMedium'/);
  assert.match(widget, /environment\.widgetFamily === 'systemLarge'/);
  assert.match(widget, /environment\.widgetFamily === 'accessoryRectangular'/);

  const workspace = await readFile('src/components/RealWorkspace.tsx', 'utf8');
  assert.match(workspace, /syncWidgetFromApi\(token\)/);
  assert.match(workspace, /deleteAccount/);
  assert.match(workspace, /Nhập XÓA để xác nhận/);
  assert.match(workspace, /Switch/);
  assert.match(workspace, /saveAiDataSharingConsent/);
  const sync = await readFile('src/widgets/widgetSync.ts', 'utf8');
  assert.match(sync, /getTasks\(token\)/);
  assert.match(sync, /listCalendarEvents/);
  assert.match(sync, /buildWidgetSnapshot/);
  assert.match(sync, /\(task\.detail \|\| ''\)\.slice/);
  assert.doesNotMatch(sync, /listNotifications|habit|weather/i);

  const backgroundTask = await readFile('src/widgets/widgetBackgroundTask.ts', 'utf8');
  assert.match(backgroundTask, /TaskManager\.defineTask/);
  assert.match(backgroundTask, /WIDGET_SYNC_INTERVAL_MINUTES = 60/);
  assert.match(backgroundTask, /minimumInterval: WIDGET_SYNC_INTERVAL_MINUTES/);
  assert.match(backgroundTask, /syncWidgetFromApi/);

  const app = await readFile('App.tsx', 'utf8');
  assert.match(app, /registerWidgetBackgroundSync/);
  assert.match(workspace, /Widget màn hình khóa/);
  assert.match(workspace, /TaskFileImportSheet/);

  const intake = await readFile('src/components/TaskFileImportSheet.tsx', 'utf8');
  assert.match(intake, /DocumentPicker\.getDocumentAsync/);
  assert.match(intake, /KeyboardAvoidingView/);
  assert.match(intake, /onScrollBeginDrag=\{Keyboard\.dismiss\}/);
  assert.match(intake, /Không thể mở trình chọn tệp/);
  assert.match(intake, /uploadTaskImportFiles/);
  assert.match(intake, /createTaskFromSuggestion/);

  const product = await readFile('src/components/MobileProduct.tsx', 'utf8');
  assert.match(product, /useShareIntentContext/);
  assert.match(product, /normalizeSharedTaskFiles/);
});
