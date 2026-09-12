# App Store resubmission

The rejected build must not be resubmitted. Build a new iOS binary from this
source and replace every public claim that can be read as an App Store rating,
review count, ranking, award, or third-party endorsement.

## Required App Store Connect changes

- Remove `AI Productivity Assistant 4.9 • 12K+ đánh giá trên App Store` from
  every metadata field, screenshot, preview video, promotional image, and
  custom product page.
- Do not replace it with an unverified rating, review count, download count,
  ranking, award, or testimonial.
- Verify Vietnamese and English metadata independently, including subtitle,
  promotional text, description, release notes, and in-app-event text.
- Upload screenshots from the new build only; they must show actual Mondaiy
  product screens and no simulated App Store listing.

## Binary verification

- Build `1.0.2 (11)` with the app source in this directory.
- Run `npm test` and `npm run typecheck` before upload.
- On a physical iPhone, send the first chat question, create a briefing
  schedule, pull to refresh the task inbox, and check each lock-screen widget
  family.

## Review reply draft

We removed the misleading rating and review-count claim from the app-facing
materials and replaced the affected screenshots with captures from the current
build. The submitted binary no longer presents App Store ratings, review
counts, rankings, awards, or third-party endorsements that cannot be verified.
