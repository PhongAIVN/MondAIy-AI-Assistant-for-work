import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const artifact = join(root, 'public/downloads/mondaiy-extension-chrome.zip');

describe('published extension download', () => {
  it('is a non-empty ZIP, not a placeholder file', () => {
    const header = readFileSync(artifact).subarray(0, 4);
    assert.deepEqual([...header], [0x50, 0x4b, 0x03, 0x04]);
    assert.ok(statSync(artifact).size > 100_000, 'extension ZIP nhỏ bất thường');
  });

  it('contains a load-unpacked Manifest V3 extension', () => {
    const files = execFileSync('unzip', ['-Z1', artifact], { encoding: 'utf8' }).split('\n');
    assert.ok(files.includes('manifest.json'));
    assert.ok(files.includes('background.js'));
    assert.ok(files.includes('sidepanel.html'));

    const manifest = JSON.parse(
      execFileSync('unzip', ['-p', artifact, 'manifest.json'], { encoding: 'utf8' }),
    ) as { manifest_version?: number; name?: string };
    assert.equal(manifest.manifest_version, 3);
    assert.equal(manifest.name, 'mondaiy');
  });

  it('is reachable from the public route and marketing navigation', () => {
    const app = readFileSync(join(root, 'src/App.tsx'), 'utf8');
    const layout = readFileSync(join(root, 'src/components/layout/MarketingLayout.tsx'), 'utf8');
    assert.match(app, /path="extension" element=\{<ExtensionInstallPage \/>\}/);
    assert.match(layout, /to: '\/extension'/);
  });
});
