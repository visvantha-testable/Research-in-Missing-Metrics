module.exports = [
  {
    files: ['**/cases/**/*.{js,mjs,cjs}'],
    ignores: ['**/eslint.config.cjs', '**/.eslintrc.json'],
    languageOptions: { ecmaVersion: 'latest', sourceType: 'commonjs' },
    rules: {
            "spaced-comment": "warn",
            "multiline-comment-style": [
                  "warn",
                  "starred-block"
            ],
            "capitalized-comments": "off",
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
