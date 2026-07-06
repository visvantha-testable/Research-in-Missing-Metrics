module.exports = [
  {
    files: ['**/*.{js,mjs,cjs}'],
    ignores: ['**/eslint.config.cjs', '**/.eslintrc.json'],
    languageOptions: { ecmaVersion: 'latest', sourceType: 'commonjs' },
    rules: {
            "max-params": [
                  "error",
                  5
            ]
      },
  },
];
