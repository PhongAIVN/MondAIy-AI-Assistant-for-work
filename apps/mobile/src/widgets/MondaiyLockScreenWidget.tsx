import { HStack, Text, VStack } from '@expo/ui/swift-ui';
import { font, foregroundStyle } from '@expo/ui/swift-ui/modifiers';
import { createWidget } from 'expo-widgets';

type WidgetDay = { label: string; date: string; count: number; isToday: boolean };
type WidgetTask = { title: string; detail: string; suggested: boolean };

export type LockScreenWidgetData = {
  nextTitle: string;
  nextTime: string;
  openTasks: number;
  week: WidgetDay[];
  schedule: Array<{ time: string; title: string }>;
  tasks: WidgetTask[];
  updatedAt: string;
};

const initialData: LockScreenWidgetData = {
  nextTitle: 'Mở Mondaiy để đồng bộ',
  nextTime: '—',
  openTasks: 0,
  week: [],
  schedule: [],
  tasks: [],
  updatedAt: '',
};

const weekFallback = (): WidgetDay[] => Array.from({ length: 7 }, (_, index) => ({ label: index === 6 ? 'CN' : `T${index + 2}`, date: '—', count: 0, isToday: false }));
const joinSchedule = (schedule: LockScreenWidgetData['schedule']) => schedule.slice(0, 3).map((item) => `${item.time} ${item.title}`).join(' · ');
const joinTasks = (tasks: WidgetTask[]) => tasks.slice(0, 4).map((task) => `${task.suggested ? 'Gợi ý' : 'Việc'}: ${task.title}${task.detail ? ` (${task.detail})` : ''}`).join(' · ');
const compactTitle = (title: string, maxLength = 30) => title.length > maxLength ? `${title.slice(0, maxLength - 1)}…` : title;

const MondaiyLockScreen = (data: LockScreenWidgetData, environment: { widgetFamily: string }) => {
  'widget';
  const title = data.nextTitle || initialData.nextTitle;
  const days = data.week.length ? data.week.slice(0, 7) : weekFallback();
  const firstTask = data.tasks[0];

  if (environment.widgetFamily === 'accessoryCircular') {
    return <VStack spacing={0}><Text modifiers={[font({ weight: 'bold', size: 20 })]}>{data.openTasks}</Text><Text modifiers={[font({ weight: 'medium', size: 8 })]}>CẦN LÀM</Text></VStack>;
  }

  if (environment.widgetFamily === 'accessoryInline') {
    return <Text modifiers={[font({ weight: 'medium', size: 13 })]}>Mondaiy · {data.openTasks} việc · {data.nextTime} {compactTitle(title, 24)}</Text>;
  }

  if (environment.widgetFamily === 'accessoryRectangular') {
    const taskSummary = data.tasks.slice(0, 2).map((task) => compactTitle(task.title, 19)).join(' · ');
    return <VStack spacing={2}><HStack spacing={5}><Text modifiers={[font({ weight: 'bold', size: 11 })]}>HÔM NAY</Text><Text modifiers={[font({ weight: 'medium', size: 10 }), foregroundStyle('#B8C5C0')]}>{data.openTasks} việc mở</Text></HStack><HStack spacing={5}><Text modifiers={[font({ weight: 'bold', size: 13 })]}>{data.nextTime}</Text><Text modifiers={[font({ weight: 'medium', size: 13 })]}>{compactTitle(title, 26)}</Text></HStack><Text modifiers={[font({ weight: 'medium', size: 10 }), foregroundStyle('#D2DDD5')]}>{taskSummary || 'Chưa có việc ưu tiên hôm nay'}</Text></VStack>;
  }

  if (environment.widgetFamily === 'systemSmall') {
    return <VStack spacing={4}><Text modifiers={[font({ weight: 'bold', size: 12 })]}>HÔM NAY</Text><Text modifiers={[font({ weight: 'bold', size: 20 })]}>{data.openTasks} việc</Text><Text modifiers={[font({ weight: 'medium', size: 11 })]}>{data.nextTime} · {title}</Text><Text modifiers={[font({ weight: 'medium', size: 10 }), foregroundStyle('#65706B')]}>{firstTask ? `✓ ${firstTask.title}` : 'Chưa có việc cần làm'}</Text></VStack>;
  }

  if (environment.widgetFamily === 'systemMedium') {
    return <VStack spacing={6}><HStack spacing={8}><Text modifiers={[font({ weight: 'bold', size: 12 })]}>LỊCH TUẦN</Text><Text modifiers={[font({ weight: 'medium', size: 11 }), foregroundStyle('#65706B')]}>Mondaiy</Text></HStack><HStack spacing={7}>{days.map((day, index) => <VStack key={`day-${index}`} spacing={2}><Text modifiers={[font({ weight: 'medium', size: 9 }), foregroundStyle(day.isToday ? '#2F7D64' : '#65706B')]}>{day.label}</Text><Text modifiers={[font({ weight: 'bold', size: 12 })]}>{day.date}</Text><Text modifiers={[font({ weight: 'bold', size: 11 }), foregroundStyle(day.count ? '#2F7D64' : '#9AA39F')]}>{day.count ? '●'.repeat(Math.min(day.count, 3)) : '—'}</Text></VStack>)}</HStack><HStack spacing={6}><Text modifiers={[font({ weight: 'bold', size: 13 })]}>{data.nextTime}</Text><Text modifiers={[font({ weight: 'medium', size: 13 })]}>{title}</Text></HStack></VStack>;
  }

  if (environment.widgetFamily === 'systemLarge') {
    return <VStack spacing={7}><HStack spacing={8}><Text modifiers={[font({ weight: 'bold', size: 14 })]}>LỊCH & VIỆC CỦA BẠN</Text><Text modifiers={[font({ weight: 'medium', size: 10 }), foregroundStyle('#65706B')]}>Cập nhật {data.updatedAt || '—'}</Text></HStack><Text modifiers={[font({ weight: 'bold', size: 12 })]}>LỊCH TUẦN NÀY</Text><HStack spacing={7}>{days.map((day, index) => <VStack key={`large-day-${index}`} spacing={1}><Text modifiers={[font({ weight: 'medium', size: 8 }), foregroundStyle(day.isToday ? '#2F7D64' : '#65706B')]}>{day.label}</Text><Text modifiers={[font({ weight: 'bold', size: 12 })]}>{day.date}</Text><Text modifiers={[font({ weight: 'bold', size: 10 }), foregroundStyle(day.count ? '#2F7D64' : '#9AA39F')]}>{day.count ? '●'.repeat(Math.min(day.count, 2)) : '—'}</Text></VStack>)}</HStack><Text modifiers={[font({ weight: 'bold', size: 12 })]}>HÔM NAY · {data.schedule.length} LỊCH HẸN</Text><Text modifiers={[font({ weight: 'medium', size: 12 }), foregroundStyle('#65706B')]}>{data.schedule.length ? joinSchedule(data.schedule) : 'Chưa có lịch hẹn hôm nay.'}</Text><Text modifiers={[font({ weight: 'bold', size: 12 })]}>VIỆC CẦN LÀM · {data.openTasks} VIỆC MỞ</Text><Text modifiers={[font({ weight: 'medium', size: 12 }), foregroundStyle('#65706B')]}>{data.tasks.length ? joinTasks(data.tasks) : 'Chưa có việc mở.'}</Text></VStack>;
  }

  return <VStack spacing={4}><HStack spacing={6}><Text modifiers={[font({ weight: 'bold', size: 11 })]}>MONDAIY · NHỊP CỦA BẠN</Text><Text modifiers={[font({ weight: 'medium', size: 10 }), foregroundStyle('#B8C5C0')]}>{data.openTasks} việc mở</Text></HStack><HStack spacing={6}><Text modifiers={[font({ weight: 'bold', size: 14 })]}>{data.nextTime}</Text><Text modifiers={[font({ weight: 'medium', size: 14 })]}>{compactTitle(title)}</Text></HStack><HStack spacing={5}><Text modifiers={[font({ weight: 'bold', size: 10 }), foregroundStyle('#86C8B1')]}>{firstTask?.suggested ? 'GỢI Ý' : 'VIỆC'}</Text><Text modifiers={[font({ weight: 'medium', size: 11 }), foregroundStyle('#D2DDD5')]}>{firstTask ? compactTitle(firstTask.title, 34) : 'Mở Mondaiy để xem kế hoạch hôm nay'}</Text></HStack></VStack>;
};

const lockScreenWidget = createWidget<LockScreenWidgetData>('MondaiyLockScreen', MondaiyLockScreen);
let currentData = initialData;

export const updateLockScreenWidget = (data: Partial<LockScreenWidgetData>) => {
  try {
    currentData = { ...currentData, ...data };
    lockScreenWidget.updateSnapshot(currentData);
  } catch { /* Expo Go không có WidgetKit target. */ }
};

export const clearLockScreenWidget = () => {
  try {
    currentData = initialData;
    lockScreenWidget.updateSnapshot(currentData);
  } catch { /* Expo Go không có WidgetKit target. */ }
};

export default lockScreenWidget;
