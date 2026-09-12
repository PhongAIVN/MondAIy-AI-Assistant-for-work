import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { MAX_TASK_IMPORT_FILE_BYTES, normalizeSharedTaskFiles, validateTaskImportFiles } from '../src/fileIntake.ts';

describe('shared task-file intake', () => {
  it('normalizes a file received from the native share sheet', () => {
    assert.deepEqual(normalizeSharedTaskFiles([{ path: 'file:///tmp/ke-hoach.docx', fileName: 'ke-hoach.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', size: 512 }]), [{ uri: 'file:///tmp/ke-hoach.docx', name: 'ke-hoach.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', size: 512 }]);
  });

  it('accepts DOCX and XLSX but rejects unsupported, empty, oversized, and excessive selections', () => {
    assert.equal(validateTaskImportFiles([{ uri: 'file:///a.docx', name: 'a.docx', mimeType: 'application/octet-stream', size: 1 }, { uri: 'file:///b.xlsx', name: 'b.xlsx', mimeType: 'application/octet-stream', size: MAX_TASK_IMPORT_FILE_BYTES }]), null);
    assert.match(validateTaskImportFiles([]) || '', /ít nhất/i);
    assert.match(validateTaskImportFiles([{ uri: 'file:///a.pdf', name: 'a.pdf', mimeType: 'application/pdf', size: 1 }]) || '', /DOCX hoặc Excel/i);
    assert.match(validateTaskImportFiles([{ uri: 'file:///a.xlsx', name: 'a.xlsx', mimeType: 'application/octet-stream', size: MAX_TASK_IMPORT_FILE_BYTES + 1 }]) || '', /200 KB/i);
    assert.match(validateTaskImportFiles(Array.from({ length: 6 }, (_, index) => ({ uri: `file:///${index}.docx`, name: `${index}.docx`, mimeType: 'application/octet-stream', size: 1 }))) || '', /tối đa 5/i);
  });
});
