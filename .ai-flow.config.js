export default {
  preset: 'balanced',
  platform: 'codeflicker',
  version: '0.4.16',
  generatedAt: new Date().toISOString(),

  project: {
    type: 'multi-module',
    name: 'ai-os',
    modules: ['frontend', 'app-controller', 'aiclient2api'],
    cssStack: 'tailwind',
    typescript: true,
  },

  commands: {
    frontend: {
      dev: 'cd frontend && pnpm dev',
      build: 'cd frontend && pnpm build',
      test: 'cd frontend && pnpm test',
      lint: 'cd frontend && pnpm lint',
    },
    'app-controller': {
      dev: 'cd app-controller && python main.py',
      test: 'cd app-controller && pytest',
      lint: 'cd app-controller && ruff check .',
    },
    'aiclient2api': {
      dev: 'cd aiclient2api && node index.js',
    },
  },

  directories: {
    platformDir: '.codeflicker',
    docs: 'docs',
    agent: 'docs/agent',
    research: 'docs/research',
    tasks: 'docs/tasks',
    snippets: '.codeflicker/snippets',
  },

  rdAssetReview: {
    enabled: true,
    outputDir: 'docs/research',
    snippetsDir: '.codeflicker/snippets',
    snippetLimit: 80,
    categories: ['components', 'composables', 'api', 'stores', 'views'],
  },

  features: {
    i18n: false,
    accessibility: true,
    performance: true,
    tailwind: true,
  },
};
