struct LargeStruct {
    char data[512];
    int flag;
};

static void consume(struct LargeStruct s) {
    s.flag = 1;
}

int trigger_passed_by_value(struct LargeStruct input) {
    consume(input);
    return input.flag;
}
