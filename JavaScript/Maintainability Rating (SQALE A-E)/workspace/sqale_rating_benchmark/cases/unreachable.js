export function unreachableDemo(flag) {
  if (flag) {
    return 1;
    const unreachable = 99;
    return unreachable;
  }
  return 0;
}
