#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const artifactDir = process.argv[2] || path.resolve(__dirname, "../.output/chrome-mv3");
const buildMode = process.argv[3] || "production";

console.log(`[Gate] Checking extension artifact at: ${artifactDir}`);
console.log(`[Gate] Mode: ${buildMode}`);

if (!fs.existsSync(artifactDir)) {
  console.error(`[FAIL] Không tìm thấy thư mục artifact: ${artifactDir}`);
  process.exit(1);
}

// 1. Kiểm tra manifest.json
const manifestPath = path.join(artifactDir, "manifest.json");
if (!fs.existsSync(manifestPath)) {
  console.error(`[FAIL] Không tìm thấy manifest.json tại: ${manifestPath}`);
  process.exit(1);
}

let manifest;
try {
  manifest = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));
} catch (err) {
  console.error(`[FAIL] Không thể parse manifest.json: ${err.message}`);
  process.exit(1);
}

if (manifest.manifest_version !== 3) {
  console.error(`[FAIL] manifest_version phải là 3 (nhận được: ${manifest.manifest_version})`);
  process.exit(1);
}

if (!manifest.version || typeof manifest.version !== "string" || !/^\d+(\.\d+)+$/.test(manifest.version)) {
  console.error(`[FAIL] version không hợp lệ trong manifest.json: ${manifest.version}`);
  process.exit(1);
}

const REQUIRED_PERMISSIONS = [
  "storage",
  "notifications",
  "alarms",
  "scripting",
  "tabs",
  "tabCapture",
  "offscreen",
  "sidePanel",
];

const manifestPermissions = new Set(manifest.permissions || []);
for (const perm of REQUIRED_PERMISSIONS) {
  if (!manifestPermissions.has(perm)) {
    console.error(`[FAIL] Thiếu required permission trong manifest.json: "${perm}"`);
    process.exit(1);
  }
}

const hostPermissions = new Set(manifest.host_permissions || []);
if (!hostPermissions.has("<all_urls>")) {
  console.error(`[FAIL] Thiếu host_permission "<all_urls>" trong manifest.json`);
  process.exit(1);
}

// Kiểm tra icon files
if (manifest.icons) {
  for (const [size, iconRelPath] of Object.entries(manifest.icons)) {
    const fullIconPath = path.join(artifactDir, iconRelPath);
    if (!fs.existsSync(fullIconPath)) {
      console.error(`[FAIL] Không tìm thấy icon size ${size} tại: ${fullIconPath}`);
      process.exit(1);
    }
  }
}

console.log(`[PASS] Manifest V3 hợp lệ (version: ${manifest.version}, permissions: ${REQUIRED_PERMISSIONS.join(", ")})`);

// Thu thập tất cả các file trong artifact để scan
function getAllFiles(dir, fileList = []) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      getAllFiles(fullPath, fileList);
    } else {
      fileList.push(fullPath);
    }
  }
  return fileList;
}

const allArtifactFiles = getAllFiles(artifactDir);

// 2. Kiểm tra modulepreload trong file HTML
const htmlFiles = allArtifactFiles.filter((f) => f.endsWith(".html"));
for (const htmlFile of htmlFiles) {
  const content = fs.readFileSync(htmlFile, "utf-8");
  if (/<link[^>]+rel=["']modulepreload["']/i.test(content)) {
    console.error(`[FAIL] Phát hiện thẻ modulepreload trong ${htmlFile} (gây cross-world mismatch)`);
    process.exit(1);
  }
}
console.log(`[PASS] HTML không có thẻ modulepreload gây lỗi cross-world`);

// 3. Kiểm tra Production URLs & Endpoints
if (buildMode === "production") {
  const textFiles = allArtifactFiles.filter((f) =>
    /\.(html|js|json|css)$/i.test(f)
  );

  for (const file of textFiles) {
    const content = fs.readFileSync(file, "utf-8");
    const localhostMatch = content.match(/https?:\/\/(localhost|127\.0\.0\.1)(:[0-9]+)?/i);
    if (localhostMatch) {
      console.error(`[FAIL] Phát hiện local endpoint "${localhostMatch[0]}" trong production artifact: ${file}`);
      process.exit(1);
    }
  }
  console.log(`[PASS] Không phát hiện localhost / 127.0.0.1 trong production artifact`);

  const expectedEndpoints = [
    process.env.WXT_API_BASE_URL || "https://p004-api.duckdns.org",
    process.env.WXT_WEB_APP_URL || "https://www.c3-app-004.io.vn",
  ];

  for (const endpoint of expectedEndpoints) {
    let found = false;
    for (const file of textFiles) {
      const content = fs.readFileSync(file, "utf-8");
      if (content.includes(endpoint)) {
        found = true;
        break;
      }
    }
    if (!found) {
      console.error(`[FAIL] Không tìm thấy production endpoint trong artifact: ${endpoint}`);
      process.exit(1);
    }
  }
  console.log(`[PASS] Tìm thấy đầy đủ production endpoints: ${expectedEndpoints.join(", ")}`);

  // 4. Secret leak sanity check
  const SECRET_PATTERNS = [
    { name: "OpenAI API Key", regex: /\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}\b/ },
    { name: "Gemini / Google API Key", regex: /\bAIzaSy[A-Za-z0-9_-]{33}\b/ },
    { name: "AWS Secret Access Key", regex: /\bAKIA[0-9A-Z]{16}\b/ },
    { name: "Private Key Header", regex: /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/ },
  ];

  for (const file of textFiles) {
    const content = fs.readFileSync(file, "utf-8");
    for (const { name, regex } of SECRET_PATTERNS) {
      if (regex.test(content)) {
        console.error(`[FAIL] Nghi vấn leak ${name} trong production artifact: ${file}`);
        process.exit(1);
      }
    }
  }
  console.log(`[PASS] Sanity check secrets: Không có API key / Private Key lộ trong bundle`);
}

console.log(`\n========================================`);
console.log(`>>> ARTIFACT RELEASE GATE: PASSED <<<`);
console.log(`========================================\n`);
process.exit(0);
