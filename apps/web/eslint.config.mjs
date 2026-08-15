import nextCoreWebVitals from 'eslint-config-next/core-web-vitals';
import nextTypescript from 'eslint-config-next/typescript';

const config = [
  ...nextCoreWebVitals,
  ...nextTypescript,
  {
    ignores: [
      'playwright-report/**',
      'test-results/**',
      'src/lib/api/generated/**',
      'tsconfig.tsbuildinfo',
    ],
  },
];

export default config;
