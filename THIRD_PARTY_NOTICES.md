# Third-party notices

NAVAREA2UC contains or depends on third-party software. Each component
listed below remains subject to its own license. This project does not
relicense those components under the proprietary terms in LICENSE.

The authoritative dependency manifests are:

- `artifacts/navarea2uc-imported-design/package.json`
- `artifacts/navarea2uc-imported-design/package-lock.json`

## Direct dependencies used by the imported web artifact

### MIT

The following direct dependencies identify MIT-licensed package
metadata in the current installation:

- React, React DOM, React Hook Form, React Day Picker, React Resizable Panels
- Radix UI component packages
- Vite, `@vitejs/plugin-react`, Tailwind CSS, `@tailwindcss/vite`
- `@hookform/resolvers`, `chokidar`, `clsx`, `cmdk`, `date-fns`
- `embla-carousel-react`, `fast-glob`, `framer-motion`, `input-otp`
- `next-themes`, `react-day-picker`, `recharts`, `sonner`
- `tailwind-merge`, `tailwindcss-animate`, `tw-animate-css`, `vaul`, `zod`
- `@types/node`, `@types/react`, and `@types/react-dom`

### ISC

- `lucide-react`

### Apache-2.0

- `class-variance-authority`
- `typescript`

### Package-specific review

The following Replit Vite plugins are included in the artifact
manifest. Review their package metadata and any bundled notices before
redistributing a production bundle:

- `@replit/vite-plugin-cartographer`
- `@replit/vite-plugin-dev-banner`
- `@replit/vite-plugin-runtime-error-modal`

## Compliance notes

1. Keep this register synchronized with dependency changes.
2. Preserve copyright and license notices required by each package.
3. Review transitive dependencies before a commercial distribution.
4. Do not apply the repository's proprietary notice to third-party
   code that is separately licensed.