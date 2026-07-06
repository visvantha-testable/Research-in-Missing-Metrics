function mixedParameters(posOnly, regular, kwOnly, ...args) {
  return posOnly + regular + kwOnly + args.reduce((sum, value) => sum + value, 0);
}

function onlyVarargs(...items) {
  return items.reduce((sum, value) => sum + value, 0);
}

module.exports = { mixedParameters, onlyVarargs };
