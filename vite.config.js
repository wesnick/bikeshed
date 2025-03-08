import {defineConfig} from 'vite';
import {resolve} from 'path';
import {cpSync} from 'fs';

export default defineConfig({
    build: {
        outDir: 'build',
        emptyOutDir: true,
        rollupOptions: {
            input: {
                app: 'js/app.js',
            },
            output: {
                entryFileNames: `[name].js`,
                chunkFileNames: `[name]-[hash].js`,
                assetFileNames: `assets/[name]-[hash].[ext]`
            }
        },
        sourcemap: true
    },
    plugins: [
        {
            name: 'copy-favicons',
            enforce: 'post',
            apply: 'build',
            closeBundle: () => {
                // Define source and destination paths
                const srcDir = resolve(__dirname, 'style');
                const destDir = resolve(__dirname, 'build');
                  const srcIco = resolve(srcDir, 'favicon.ico')
                const destIco = resolve(destDir, 'favicon.ico');

                // Copy files
                cpSync(srcIco, destIco, {overwrite: true});
                console.log('Favicons copied successfully!');
            }
        }
    ]
});