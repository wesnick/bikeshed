import {defineConfig} from 'vite';
import {resolve} from 'path';
import {cpSync, existsSync, mkdirSync} from 'fs';
import inject from '@rollup/plugin-inject';

export default defineConfig({
    build: {
        outDir: 'build/js',
        emptyOutDir: false, // Don't empty the entire build directory
        rollupOptions: {
            input: {
                app: 'js/app.js',
            },
            output: {
                entryFileNames: `[name].js`,
                chunkFileNames: `[name]-[hash].js`,
                assetFileNames: `assets/[name]-[hash].[ext]`
            },
      onwarn(warning, warn) {
        // Suppress specific eval warnings for htmx.org
        if (
          warning.code === 'EVAL' && 
          warning.id && 
          warning.id.includes('htmx.org')
        ) {
          return
        }
        // Forward all other warnings to the default handler
        warn(warning)
      }
        },
        sourcemap: true
    },
    plugins: [
        inject({
           htmx: 'htmx.org'
        }),
        {
            name: 'prepare-build-dir',
            apply: 'build',
            buildStart: () => {
                // Ensure build directory exists
                const buildDir = resolve(__dirname, 'build');
                if (!existsSync(buildDir)) {
                    mkdirSync(buildDir, { recursive: true });
                }
                
                // Ensure js directory exists
                const jsDir = resolve(buildDir, 'js');
                if (!existsSync(jsDir)) {
                    mkdirSync(jsDir, { recursive: true });
                }
                
                // Ensure css directory exists
                const cssDir = resolve(buildDir, 'css');
                if (!existsSync(cssDir)) {
                    mkdirSync(cssDir, { recursive: true });
                }
            }
        },
        {
            name: 'copy-favicons',
            enforce: 'post',
            apply: 'build',
            closeBundle: () => {
                // Define source and destination paths
                const srcDir = resolve(__dirname, 'style');
                const destDir = resolve(__dirname, 'build');
                const srcIco = resolve(srcDir, 'favicon.ico');
                const destIco = resolve(destDir, 'favicon.ico');

                // Copy files
                cpSync(srcIco, destIco, {overwrite: true});
                console.log('Favicons copied successfully!');
            }
        }
    ]
});
