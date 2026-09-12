# Android staging APK EAS profile

- Objective: Add an EAS staging profile that produces an internal Android APK.
- Research sources: `apps/mobile/eas.json`.
- Scope: Added `build.staging` with `developmentClient: false`, `distribution: internal`, and `android.buildType: apk`.
- Base/head SHA: local working tree change from current `main`.
- Observable behavior: `eas build --platform android --profile staging` will target an APK artifact instead of an AAB.
- Files changed: `apps/mobile/eas.json`.
- Verification:
  - `node -e "JSON.parse(require('fs').readFileSync('apps/mobile/eas.json','utf8')); console.log('apps/mobile/eas.json OK')"`: pass.
- Skipped checks: No app code changed; mobile test/typecheck not required for EAS profile-only change.
- Risk: Low. Existing development, preview, production, and submit profiles were left unchanged.
- Deploy status: Not built or submitted in this change.
- Rollback: Remove `build.staging` from `apps/mobile/eas.json`.
