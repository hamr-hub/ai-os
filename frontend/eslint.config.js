import tseslint from '@typescript-eslint/eslint-plugin'
import tsParser from '@typescript-eslint/parser'
import vue from 'eslint-plugin-vue'
import vueParser from 'vue-eslint-parser'
import prettier from 'eslint-config-prettier/flat'

export default [
  {
    ignores: ['node_modules/**', 'dist/**', 'dist_30000/**', 'dist-ssr/**', '*.local.ts', 'e2e-manual-test.cjs'],
  },
  ...vue.configs['flat/recommended'],
  {
    files: ['**/*.{js,jsx,cjs,mjs,ts,tsx,cts,mts,vue}'],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: tsParser,
        ecmaVersion: 'latest',
        sourceType: 'module',
        ecmaFeatures: {
          jsx: true,
        },
      },
      globals: {
        window: 'readonly',
        document: 'readonly',
        navigator: 'readonly',
        console: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        AbortController: 'readonly',
        HTMLElement: 'readonly',
        HTMLTextAreaElement: 'readonly',
        KeyboardEvent: 'readonly',
        MouseEvent: 'readonly',
      },
    },
    plugins: {
      '@typescript-eslint': tseslint,
    },
    rules: {
      ...tseslint.configs.recommended.rules,
      ...prettier.rules,
      'vue/multi-word-component-names': 'off',
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      'no-undef': 'off',
      'vue/no-v-html': 'warn',
    },
  },
]
