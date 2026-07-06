int shadow_demo(int outer) {
    int x = outer;
    {
        int x = 2;
        x += 1;
    }
    return x;
}
