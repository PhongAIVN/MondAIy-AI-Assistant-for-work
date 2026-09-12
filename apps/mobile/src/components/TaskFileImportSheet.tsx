import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Keyboard, KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as DocumentPicker from 'expo-document-picker';
import { createTaskFromSuggestion, uploadTaskImportFiles, type TaskImportProposal } from '../api/client';
import { normalizeSharedTaskFiles, validateTaskImportFiles, type TaskImportFile } from '../fileIntake';

type Props = {
  visible: boolean;
  token: string;
  sharedFiles?: TaskImportFile[];
  onClose: () => void;
  onImported: () => void;
};

const taskPickerTypes = [
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
];

export function TaskFileImportSheet({ visible, token, sharedFiles = [], onClose, onImported }: Props) {
  const [files, setFiles] = useState<TaskImportFile[]>([]);
  const [searchName, setSearchName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<Awaited<ReturnType<typeof uploadTaskImportFiles>> | null>(null);
  const [created, setCreated] = useState<Set<string>>(new Set());

  const fileKey = useMemo(() => sharedFiles.map((file) => `${file.uri}:${file.name}`).join('|'), [sharedFiles]);
  useEffect(() => {
    if (!visible) return;
    setFiles(sharedFiles);
    setResult(null);
    setError('');
    setCreated(new Set());
  }, [visible, fileKey]);

  const chooseFiles = async () => {
    try {
      const picked = await DocumentPicker.getDocumentAsync({ type: taskPickerTypes, multiple: true, copyToCacheDirectory: true });
      if (picked.canceled) return;
      const next = picked.assets.map((asset) => ({
        uri: asset.uri,
        name: asset.name,
        mimeType: asset.mimeType || 'application/octet-stream',
        size: asset.size ?? null,
      }));
      setFiles(next);
      setResult(null);
      setError('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể mở trình chọn tệp.');
    }
  };

  const importFiles = async () => {
    const validationError = validateTaskImportFiles(files);
    if (validationError) { setError(validationError); return; }
    setLoading(true);
    setError('');
    try {
      setResult(await uploadTaskImportFiles(files, token, searchName));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể xử lý tệp.');
    } finally {
      setLoading(false);
    }
  };

  const addProposal = async (proposal: TaskImportProposal) => {
    const key = proposal.externalKey || `${proposal.rowNumber}:${proposal.title}`;
    setLoading(true);
    setError('');
    try {
      await createTaskFromSuggestion({ title: proposal.title, detail: proposal.detail, dueAt: proposal.dueAt, allDay: proposal.allDay }, token);
      setCreated((current) => new Set(current).add(key));
      onImported();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể tạo bản nháp công việc.');
    } finally {
      setLoading(false);
    }
  };

  return <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
    <View style={styles.backdrop}>
      <View style={styles.sheet}>
        <View style={styles.header}>
          <View style={styles.headerIcon}><Ionicons name="document-text-outline" size={22} color="#356F83" /></View>
          <View style={styles.flex}><Text style={styles.title}>Nhập việc từ tệp</Text><Text style={styles.subtitle}>DOCX hoặc Excel</Text></View>
          <Pressable accessibilityRole="button" accessibilityLabel="Đóng nhập tệp" style={styles.close} onPress={onClose}><Ionicons name="close" size={22} color="#23404D" /></Pressable>
        </View>
        <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : 'height'} keyboardVerticalOffset={0}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled" keyboardDismissMode="interactive" onScrollBeginDrag={Keyboard.dismiss}>
          <Pressable accessibilityRole="button" style={styles.filePicker} onPress={() => void chooseFiles()}>
            <Ionicons name={files.length ? 'document-attach' : 'add-circle-outline'} size={25} color="#356F83" />
            <View style={styles.flex}><Text style={styles.filePickerTitle}>{files.length ? `${files.length} tệp đã chọn` : 'Chọn tệp'}</Text><Text numberOfLines={2} style={styles.filePickerCopy}>{files.length ? files.map((file) => file.name).join('\n') : 'Chọn từ thiết bị hoặc chia sẻ từ Zalo'}</Text></View>
            <Ionicons name="chevron-forward" size={18} color="#789096" />
          </Pressable>
          <TextInput value={searchName} onChangeText={setSearchName} placeholder="Tên cần tìm trong tệp (không bắt buộc)" placeholderTextColor="#789096" style={styles.input} editable={!loading} />
          {error ? <Text style={styles.error}>{error}</Text> : null}
          <Pressable accessibilityRole="button" disabled={loading || !files.length} style={[styles.primary, (loading || !files.length) && styles.disabled]} onPress={() => void importFiles()}>
            {loading ? <ActivityIndicator color="#FFFFDE" /> : <><Ionicons name="sparkles-outline" size={18} color="#FFFFDE" /><Text style={styles.primaryText}>Đọc tệp và đề xuất việc</Text></>}
          </Pressable>
          {result ? <View style={styles.result}>
            {result.agentResponse ? <Text style={styles.agent}>{result.agentResponse}</Text> : null}
            {result.agentWarning ? <Text style={styles.warning}>{result.agentWarning}</Text> : null}
            {result.needsNameQuery ? <Text style={styles.empty}>Chưa có việc khớp. Nhập tên rồi thử lại.</Text> : null}
            {result.proposals.map((proposal) => {
              const key = proposal.externalKey || `${proposal.rowNumber}:${proposal.title}`;
              const isCreated = created.has(key);
              return <View key={key} style={styles.proposal}>
                <View style={styles.proposalMain}><Text style={styles.proposalTitle}>{proposal.title}</Text>{proposal.detail ? <Text numberOfLines={3} style={styles.proposalDetail}>{proposal.detail}</Text> : null}{proposal.dueAt ? <Text style={styles.proposalMeta}>Hạn {new Date(proposal.dueAt).toLocaleString('vi-VN')}</Text> : null}</View>
                <Pressable accessibilityRole="button" accessibilityLabel={`Thêm ${proposal.title} thành bản nháp`} disabled={loading || isCreated} style={[styles.add, isCreated && styles.addDone]} onPress={() => void addProposal(proposal)}><Ionicons name={isCreated ? 'checkmark' : 'add'} size={19} color={isCreated ? '#2E725C' : '#FFFFDE'} /></Pressable>
              </View>;
            })}
          </View> : null}
        </ScrollView>
        </KeyboardAvoidingView>
      </View>
    </View>
  </Modal>;
}

export const fromSharedFiles = normalizeSharedTaskFiles;

const styles = StyleSheet.create({
  backdrop: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(20, 39, 47, 0.42)' },
  sheet: { maxHeight: '88%', backgroundColor: '#FFFFDE', borderTopLeftRadius: 22, borderTopRightRadius: 22, paddingTop: 18 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 11, paddingHorizontal: 20, paddingBottom: 14, borderBottomWidth: 1, borderBottomColor: '#D6E1DB' },
  headerIcon: { width: 42, height: 42, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: '#E3F1EE' },
  flex: { flex: 1 }, title: { color: '#23404D', fontSize: 18, fontWeight: '800' }, subtitle: { color: '#789096', fontSize: 12, marginTop: 2 },
  close: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' }, content: { padding: 20, paddingBottom: Platform.OS === 'ios' ? 34 : 24, gap: 12 },
  filePicker: { minHeight: 76, flexDirection: 'row', alignItems: 'center', gap: 11, padding: 13, backgroundColor: '#F2F7F4', borderWidth: 1, borderColor: '#C8D9D6', borderRadius: 10 },
  filePickerTitle: { color: '#23404D', fontSize: 14, fontWeight: '800' }, filePickerCopy: { color: '#55727A', fontSize: 12, lineHeight: 17, marginTop: 2 },
  input: { minHeight: 48, borderWidth: 1, borderColor: '#C8D9D6', borderRadius: 8, paddingHorizontal: 13, color: '#23404D', fontSize: 14, backgroundColor: '#FFFEEF' },
  primary: { minHeight: 50, backgroundColor: '#356F83', borderRadius: 8, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingHorizontal: 14 }, primaryText: { color: '#FFFFDE', fontSize: 14, fontWeight: '800' }, disabled: { opacity: 0.5 },
  error: { color: '#A4534E', fontSize: 13, lineHeight: 19 }, result: { gap: 10, marginTop: 4 }, agent: { color: '#23404D', fontSize: 14, lineHeight: 20, padding: 13, backgroundColor: '#E3F1EE', borderRadius: 8 }, warning: { color: '#8A6B2A', fontSize: 13, lineHeight: 18, padding: 11, backgroundColor: '#F6E9B8', borderRadius: 8 }, empty: { color: '#55727A', fontSize: 13, paddingVertical: 10 },
  proposal: { minHeight: 72, flexDirection: 'row', gap: 10, padding: 13, borderWidth: 1, borderColor: '#C8D9D6', borderRadius: 8, backgroundColor: '#FFFEEF' }, proposalMain: { flex: 1 }, proposalTitle: { color: '#23404D', fontSize: 14, fontWeight: '800' }, proposalDetail: { color: '#55727A', fontSize: 12, lineHeight: 17, marginTop: 3 }, proposalMeta: { color: '#356F83', fontSize: 11, marginTop: 5, fontWeight: '700' },
  add: { width: 38, height: 38, borderRadius: 8, alignItems: 'center', justifyContent: 'center', backgroundColor: '#356F83' }, addDone: { backgroundColor: '#E3F1EE' },
});
