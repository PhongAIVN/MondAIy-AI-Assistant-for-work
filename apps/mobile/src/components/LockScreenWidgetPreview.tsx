import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { listCalendarEvents, type CalendarEvent, type Task } from '../api/client';

type WidgetSection = 'week' | 'schedule' | 'tasks';
const colors = ['#65B885', '#E87570', '#E8BC58', '#9A7BD6', '#5B9FC0'];
const dayLabels = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];
const colorFor = (id: string) => colors[id.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0) % colors.length];

export function LockScreenWidgetPreview({ visible, token, tasks, onClose }: { visible: boolean; token: string; tasks: Task[]; onClose: () => void }) {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [sections, setSections] = useState<WidgetSection[]>(['week', 'schedule', 'tasks']);
  const range = useMemo(() => {
    const from = new Date(); from.setHours(0, 0, 0, 0); from.setDate(from.getDate() - ((from.getDay() + 6) % 7));
    const to = new Date(from); to.setDate(to.getDate() + 7);
    return { from: from.toISOString(), to: to.toISOString() };
  }, []);
  useEffect(() => {
    if (!visible) return;
    setLoading(true);
    void listCalendarEvents(range.from, range.to, token).then((body) => setEvents(body.events.sort((a, b) => a.startAt.localeCompare(b.startAt)))).finally(() => setLoading(false));
  }, [visible, range.from, range.to, token]);

  const today = new Date();
  const activeTasks = tasks.filter((task) => task.status !== 'completed' && task.status !== 'dismissed').slice(0, 3);
  const todayEvents = events.filter((event) => new Date(event.startAt).toDateString() === today.toDateString()).slice(0, 4);
  const toggle = (section: WidgetSection) => setSections((current) => current.includes(section) ? current.filter((item) => item !== section) : [...current, section]);
  const includes = (section: WidgetSection) => sections.includes(section);

  return <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
    <View style={styles.screen}>
      <View style={styles.header}><View><Text style={styles.eyebrow}>PERSONAL WIDGETS</Text><Text style={styles.title}>Lock Screen</Text><Text style={styles.copy}>Xem trước dữ liệu thật trước khi ghim widget.</Text></View><Pressable accessibilityRole="button" accessibilityLabel="Đóng xem trước widget" style={styles.close} onPress={onClose}><Ionicons name="close" size={22} color="#F7F4EA" /></Pressable></View>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.phone}><View style={styles.dynamicIsland} /><Text style={styles.phoneTime}>{today.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}</Text><Text style={styles.phoneDate}>{today.toLocaleDateString('vi-VN', { weekday: 'long', day: 'numeric', month: 'long' })}</Text>
          <View style={styles.widget}>
            <View style={styles.widgetHeader}><View><Text style={styles.widgetKicker}>MONDAIY · TODAY</Text><Text style={styles.widgetTitle}>Nhịp của bạn</Text></View><Ionicons name="sparkles" size={18} color="#DFF5E5" /></View>
            {loading ? <ActivityIndicator color="#DFF5E5" style={styles.loader} /> : <>
              {includes('week') ? <Week events={events} today={today} /> : null}
              {includes('schedule') ? <Schedule events={todayEvents} /> : null}
              {includes('tasks') ? <Tasks tasks={activeTasks} /> : null}
              {!sections.length ? <Text style={styles.empty}>Chọn ít nhất một khối ở phần tuỳ chỉnh.</Text> : null}
            </>}
          </View>
        </View>
        <View style={styles.config}><Text style={styles.configTitle}>Tuỳ chỉnh nội dung</Text><Text style={styles.configCopy}>Mỗi khối dùng dữ liệu đã đồng bộ trong tài khoản của bạn.</Text>
          {([
            ['week', 'Lịch biểu tuần', 'calendar-outline'],
            ['schedule', 'Lịch trình hôm nay', 'time-outline'],
            ['tasks', 'Việc cần làm', 'checkbox-outline'],
          ] as Array<[WidgetSection, string, keyof typeof Ionicons.glyphMap]>).map(([section, label, icon]) => <Pressable key={section} accessibilityRole="switch" accessibilityState={{ checked: includes(section) }} style={[styles.option, includes(section) && styles.optionActive]} onPress={() => toggle(section)}><Ionicons name={icon} size={20} color={includes(section) ? '#3B9470' : '#7A8587'} /><Text style={styles.optionText}>{label}</Text><Ionicons name={includes(section) ? 'checkmark-circle' : 'ellipse-outline'} size={22} color={includes(section) ? '#3B9470' : '#7A8587'} /></Pressable>)}
        </View>
        <View style={styles.notice}><Ionicons name="information-circle-outline" size={18} color="#5F91A1" /><Text style={styles.noticeText}>Đây là preview trong app. Widget hiển thị trực tiếp ngoài Lock Screen cần iOS Widget Extension trong bản native build.</Text></View>
      </ScrollView>
    </View>
  </Modal>;
}

function Week({ events, today }: { events: CalendarEvent[]; today: Date }) {
  const monday = new Date(today); monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
  return <View style={styles.section}><Text style={styles.sectionTitle}>LỊCH TUẦN</Text><View style={styles.week}>{dayLabels.map((label, index) => { const date = new Date(monday); date.setDate(monday.getDate() + index); const count = events.filter((event) => new Date(event.startAt).toDateString() === date.toDateString()).length; return <View key={label} style={styles.day}><Text style={[styles.dayName, date.toDateString() === today.toDateString() && styles.today]}>{label}</Text><Text style={styles.dayNumber}>{date.getDate()}</Text><View style={styles.dots}>{Array.from({ length: Math.min(count, 3) }, (_, dot) => <View key={dot} style={[styles.dot, { backgroundColor: colors[(index + dot) % colors.length] }]} />)}</View></View>; })}</View></View>;
}

function Schedule({ events }: { events: CalendarEvent[] }) {
  return <View style={styles.section}><Text style={styles.sectionTitle}>HÔM NAY</Text>{events.length ? events.map((event) => <View key={event.id} style={styles.row}><View style={[styles.rail, { backgroundColor: colorFor(event.id) }]} /><Text style={styles.time}>{new Date(event.startAt).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}</Text><Text numberOfLines={1} style={styles.rowText}>{event.title}</Text></View>) : <Text style={styles.muted}>Chưa có lịch Google Calendar hôm nay.</Text>}</View>;
}

function Tasks({ tasks }: { tasks: Task[] }) {
  return <View style={styles.section}><Text style={styles.sectionTitle}>VIỆC CẦN LÀM</Text>{tasks.length ? tasks.map((task) => <View key={task.id} style={styles.row}><Ionicons name={task.status === 'proposed' ? 'checkmark-circle-outline' : 'ellipse-outline'} size={15} color="#E8DDB7" /><Text numberOfLines={1} style={styles.rowText}>{task.title}</Text></View>) : <Text style={styles.muted}>Chưa có việc cần làm.</Text>}</View>;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#131817' }, header: { padding: 22, paddingTop: 24, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }, eyebrow: { color: '#86C8B1', fontSize: 10, fontWeight: '800', letterSpacing: 1.4 }, title: { color: '#F7F4EA', fontSize: 34, fontFamily: 'CormorantGaramond_600SemiBold', marginTop: 2 }, copy: { color: '#B8C5C0', fontSize: 13, marginTop: 3 }, close: { width: 43, height: 43, borderRadius: 22, backgroundColor: '#28302E', alignItems: 'center', justifyContent: 'center' }, scroll: { padding: 18, paddingTop: 2, paddingBottom: 42, gap: 18 }, phone: { minHeight: 560, paddingHorizontal: 18, paddingTop: 24, borderRadius: 38, backgroundColor: '#0B0D0D', borderWidth: 1, borderColor: '#3A403E', alignItems: 'center' }, dynamicIsland: { width: 112, height: 26, borderRadius: 16, backgroundColor: '#000' }, phoneTime: { color: '#F7F4EA', fontSize: 42, fontWeight: '700', marginTop: 28 }, phoneDate: { color: '#CBD4D0', fontSize: 13, marginTop: 4 }, widget: { width: '100%', marginTop: 34, borderRadius: 24, padding: 15, backgroundColor: 'rgba(45,59,55,0.94)', borderWidth: 1, borderColor: '#63746D' }, widgetHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingBottom: 10 }, widgetKicker: { color: '#A8D5C0', fontSize: 9, fontWeight: '800', letterSpacing: 1.1 }, widgetTitle: { color: '#F7F4EA', fontFamily: 'CormorantGaramond_600SemiBold', fontSize: 23, marginTop: 2 }, loader: { marginVertical: 32 }, section: { borderTopWidth: 1, borderTopColor: '#52625C', paddingTop: 10, marginTop: 4 }, sectionTitle: { color: '#B9C8C1', fontSize: 9, fontWeight: '800', letterSpacing: 1.1, marginBottom: 8 }, week: { flexDirection: 'row', justifyContent: 'space-between' }, day: { alignItems: 'center', width: 31 }, dayName: { color: '#AAB9B2', fontSize: 9, fontWeight: '700' }, today: { color: '#DFF5E5' }, dayNumber: { color: '#F7F4EA', fontSize: 14, fontWeight: '700', marginTop: 3 }, dots: { minHeight: 11, flexDirection: 'row', gap: 2, marginTop: 5 }, dot: { width: 5, height: 5, borderRadius: 3 }, row: { minHeight: 27, flexDirection: 'row', alignItems: 'center', gap: 7 }, rail: { width: 3, height: 17, borderRadius: 3 }, time: { width: 38, color: '#AAB9B2', fontSize: 10 }, rowText: { flex: 1, color: '#F7F4EA', fontSize: 12, fontWeight: '600' }, muted: { color: '#AAB9B2', fontSize: 12, paddingBottom: 3 }, empty: { color: '#AAB9B2', fontSize: 12, paddingVertical: 13 }, config: { borderRadius: 22, backgroundColor: '#F4F1E7', padding: 16 }, configTitle: { color: '#25403E', fontSize: 19, fontFamily: 'CormorantGaramond_600SemiBold' }, configCopy: { color: '#61726E', fontSize: 12, lineHeight: 17, marginTop: 3, marginBottom: 10 }, option: { minHeight: 51, borderRadius: 14, paddingHorizontal: 12, flexDirection: 'row', alignItems: 'center', gap: 10 }, optionActive: { backgroundColor: '#E0F0E7' }, optionText: { flex: 1, color: '#25403E', fontSize: 14, fontWeight: '700' }, notice: { flexDirection: 'row', gap: 8, paddingHorizontal: 8 }, noticeText: { flex: 1, color: '#AEC0BA', fontSize: 12, lineHeight: 17 },
});
