import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

describe('admin Discord announcement review', () => {
  it('renders editable title, category and action fields', () => {
    const source = readFileSync(join(root, 'src/pages/admin/AdminDiscordAnnouncementPage.tsx'), 'utf8');
    assert.match(source, /aria-label="Tiêu đề sẽ publish"/);
    assert.match(source, /aria-label="Category đề xuất"/);
    assert.match(source, /aria-label=\{`Action \$\{index \+ 1\} kind`\}/);
    assert.match(source, /aria-label=\{`Action \$\{index \+ 1\} due date`\}/);
    assert.match(source, /aria-label=\{`Action \$\{index \+ 1\} all day`\}/);
  });

  it('sends the reviewed values instead of only the LLM category', () => {
    const source = readFileSync(join(root, 'src/pages/admin/AdminDiscordAnnouncementPage.tsx'), 'utf8');
    assert.match(source, /title: item\.preview\.title/);
    assert.match(source, /items: item\.preview\.items\.map/);
    assert.match(source, /dueAt, allDay/);
  });
});
