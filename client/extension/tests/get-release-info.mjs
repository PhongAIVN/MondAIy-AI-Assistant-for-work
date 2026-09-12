#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const extDir = path.resolve(__dirname, "..");
const pkg = JSON.parse(fs.readFileSync(path.join(extDir, "package.json"), "utf8"));
const outDir = path.join(extDir, ".output");
const zipFiles = fs.existsSync(outDir) ? fs.readdirSync(outDir).filter((f) => f.endsWith(".zip")) : [];
const zipPath = zipFiles.length ? path.join(outDir, zipFiles[0]) : "";

console.log(JSON.stringify({ version: pkg.version, zipFile: zipPath, artifactDir: path.join(outDir, "chrome-mv3") }));
