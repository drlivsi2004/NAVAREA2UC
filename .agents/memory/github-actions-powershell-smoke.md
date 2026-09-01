---
name: Windows Actions smoke JSON capture
description: PowerShell handling of redirected Python JSON in Windows release smoke tests
---

Windows release smoke tests should capture Python JSON output into a PowerShell variable, preserve the Python exit code immediately, then write the captured output with explicit UTF-8 encoding before parsing it.

**Why:** Direct PowerShell redirection can hide the JSON diagnostics needed to distinguish a nonzero Python preview result, missing output, invalid encoding, and a boolean approval mismatch.

**How to apply:** Keep the approval gate strict; expose the preview exit code, reviewed fingerprint, current fingerprint, and match boolean before asserting. Serialize any deliberately stale JSON with explicit UTF-8 as well.