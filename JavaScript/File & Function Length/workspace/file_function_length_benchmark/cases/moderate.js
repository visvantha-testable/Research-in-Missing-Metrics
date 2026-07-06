/** Benchmark case: moderate function length file with multiple functions. */
function stepOne(x) {
  return x + 1;
}

function stepTwo(x) {
  return x + 2;
}

function stepThree(x) {
  return x + 3;
}

function stepFour(x) {
  return x + 4;
}

function stepFive(x) {
  return x + 5;
}

module.exports = { stepOne, stepTwo, stepThree, stepFour, stepFive };
