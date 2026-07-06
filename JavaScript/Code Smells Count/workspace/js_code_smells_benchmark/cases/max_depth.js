export function maxDepthDemo(value) {
  if (value > 0) {
    if (value > 1) {
      if (value > 2) {
        if (value > 3) {
          if (value > 4) {
            return value;
          }
        }
      }
    }
  }
  return 0;
}
