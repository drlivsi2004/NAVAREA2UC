---
name: GitHub binary transfer
description: Reliable handling of binary files through the GitHub integration in this workspace.
---

Binary files sent through a shell command's captured output can be truncated before reaching the GitHub API. Use direct filesystem reads inside the protected GitHub operation and create a base64 blob from the complete bytes.

**Why:** A truncated ICO looked like a valid file path in the branch but caused PyInstaller's Windows build to fail; the same source and intact ICO built successfully.

**How to apply:** For icons, archives, and other binary files, avoid passing large base64 strings through shell output. Read the workspace file directly in the integration operation, verify the byte count/blob, then dispatch the build.