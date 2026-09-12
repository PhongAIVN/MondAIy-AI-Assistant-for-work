import { Platform } from 'react-native';
import * as BackgroundTask from 'expo-background-task';
import * as TaskManager from 'expo-task-manager';
import { refreshSession } from '../api/client';
import { readSession, saveSession } from '../session';
import { syncWidgetFromApi } from './widgetSync';

export const WIDGET_BACKGROUND_SYNC_TASK = 'mondaiy.widget-hourly-sync';
export const WIDGET_SYNC_INTERVAL_MINUTES = 60;

// Phải được khai báo ở module scope để iOS có thể khởi tạo app không cần UI.
TaskManager.defineTask(WIDGET_BACKGROUND_SYNC_TASK, async () => {
  try {
    const session = await readSession();
    if (!session?.accessToken) return BackgroundTask.BackgroundTaskResult.Success;
    try {
      await syncWidgetFromApi(session.accessToken);
    } catch {
      const refreshed = await refreshSession(session.refreshToken);
      await saveSession(refreshed);
      await syncWidgetFromApi(refreshed.accessToken);
    }
    return BackgroundTask.BackgroundTaskResult.Success;
  } catch {
    return BackgroundTask.BackgroundTaskResult.Failed;
  }
});

export const registerWidgetBackgroundSync = async (): Promise<void> => {
  if (Platform.OS !== 'ios') return;
  await BackgroundTask.registerTaskAsync(WIDGET_BACKGROUND_SYNC_TASK, {
    minimumInterval: WIDGET_SYNC_INTERVAL_MINUTES,
  });
};

export const unregisterWidgetBackgroundSync = async (): Promise<void> => {
  if (Platform.OS !== 'ios') return;
  await BackgroundTask.unregisterTaskAsync(WIDGET_BACKGROUND_SYNC_TASK);
};
