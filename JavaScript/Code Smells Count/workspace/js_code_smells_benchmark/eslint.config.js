export default [
  {
    files: ['**/*.{js,jsx,mjs,cjs}'],
    languageOptions: { ecmaVersion: 'latest', sourceType: 'module' },
    rules: {
            "complexity": [
                  "warn",
                  10
            ],
            "max-depth": [
                  "warn",
                  4
            ],
            "max-lines-per-function": [
                  "warn",
                  50
            ],
            "max-params": [
                  "warn",
                  5
            ],
            "max-statements": [
                  "warn",
                  20
            ],
            "no-duplicate-imports": "warn",
            "no-unused-vars": "warn",
            "no-unreachable": "warn",
            "no-shadow": "warn"
      },
  },
];
