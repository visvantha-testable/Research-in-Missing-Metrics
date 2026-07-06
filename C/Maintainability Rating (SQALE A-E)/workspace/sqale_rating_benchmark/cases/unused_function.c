static void internal_helper(void) {
}

static void never_called(void) {
}

int public_api(void) {
    internal_helper();
    return 0;
}
