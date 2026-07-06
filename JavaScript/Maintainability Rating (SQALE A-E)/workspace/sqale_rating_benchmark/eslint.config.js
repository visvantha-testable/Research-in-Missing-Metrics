export default [
  {
    files: ['**/*.{js,mjs,cjs}'],
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
            "max-lines": [
                  "warn",
                  300
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
            "max-nested-callbacks": [
                  "warn",
                  3
            ]
      },
  },
];
