import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tsconfigPaths from 'vite-tsconfig-paths'

export default defineConfig({
  plugins: [react(), tsconfigPaths()],
  server: {
    port: 5173,
    fs: {
      // Allow serving files from one level above the frontend/ root.
      // Required for: import rawModels from '../../../models.config.json'
      // in frontend/src/lib/constants.ts — models.config.json lives at repo root.
      allow: ['..'],
    },
  },
})
