import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import globals from 'globals';
export default tseslint.config({ ignores: ['src/generated/**', 'dist/**', 'public/**'] }, js.configs.recommended, ...tseslint.configs.recommended, { files: ['**/*.{ts,tsx}'], languageOptions: { globals: { ...globals.browser, ...globals.node } } });
