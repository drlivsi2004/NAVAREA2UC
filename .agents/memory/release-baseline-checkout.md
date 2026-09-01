---
name: Release baseline clean-checkout validation
description: Why reviewed corpus baseline updates must be present in the checked-out commit before release validation is considered complete.
---

Reviewed corpus fingerprints and full reports must be committed before relying on clean-checkout release tests or CI validation.

**Why:** Clean-checkout tests and CI clone the committed tree, so uncommitted report updates can make the working copy pass while the checkout still sees a stale reviewed fingerprint.

**How to apply:** After an approved corpus baseline refresh, commit the reviewed full report, compact baseline, and generated preview/report artifacts, then rerun the clean-checkout tests and release gate.