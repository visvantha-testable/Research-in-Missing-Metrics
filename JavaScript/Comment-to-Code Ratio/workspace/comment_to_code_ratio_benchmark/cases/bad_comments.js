/* Non-starred block comment triggers multiline-comment-style warnings. */
function badBlockStyle() {
  return 1;
}

//missing-space after slashes
function badSpacedComment() {
  return 2;
}

module.exports = { badBlockStyle, badSpacedComment };
