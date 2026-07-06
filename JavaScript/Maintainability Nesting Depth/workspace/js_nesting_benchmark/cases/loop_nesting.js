export function loopNesting(items) {
  let total = 0;
  for (const item of items) {
    if (item > 0) {
      for (const nested of items) {
        if (nested > 10) {
          for (const deep of items) {
            if (deep > 20) {
              total += deep;
            }
          }
        }
      }
    }
  }
  return total;
}
