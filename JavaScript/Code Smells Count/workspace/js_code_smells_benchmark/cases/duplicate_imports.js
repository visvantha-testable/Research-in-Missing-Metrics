import { helperA } from './utils.js';
import { helperB } from './utils.js';

export function duplicateImportsDemo() {
  return helperA() + helperB();
}
