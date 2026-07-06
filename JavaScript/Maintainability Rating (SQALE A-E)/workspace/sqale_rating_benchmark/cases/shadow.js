export function shadowDemo(outer) {
  function inner() {
    const outer = 10;
    return outer;
  }
  return inner() + outer;
}
