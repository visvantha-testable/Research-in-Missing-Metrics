/** Benchmark case: nested control structures for nesting depth analysis. */
function nestedExample(x) {
  if (x > 0) {
    if (x > 1) {
      if (x > 2) {
        return x;
      }
    }
  }
  return 0;
}

module.exports = { nestedExample };
