import { defineConfig } from 'vite'
import { resolve } from 'path'

export default defineConfig({
    build: {
        outDir: 'build',
        emptyOutDir: true,
        rollupOptions: {
            input: {
                app: resolve(__dirname, 'js/app.js'),
            },
            output: {
                entryFileNames: `[name].js`,
                chunkFileNames: `[name]-[hash].js`,
                assetFileNames: `assets/[name]-[hash].[ext]`
            }
        },
        sourcemap: true
    }
})
