 import { defineConfig } from 'vite'

 export default defineConfig({
     build: {
         outDir: 'build/js',
         emptyOutDir: false,
         rollupOptions: {
             input: {
                 app: 'js/app.js',
             },
             output: {
                 entryFileNames: `app.js`,
                 chunkFileNames: `[name].js`,
                 assetFileNames: `[name].[ext]`
             }
         },
         sourcemap: true
     }
 })