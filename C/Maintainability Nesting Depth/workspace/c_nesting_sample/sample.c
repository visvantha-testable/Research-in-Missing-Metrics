#include <stdio.h>

int flat(int x) {
    return x + 1;
}

int depth_three(int x) {
    if (x > 0) {
        if (x > 1) {
            if (x > 2) {
                return x;
            }
        }
    }
    return 0;
}

int depth_six(int x) {
    if (x > 0) {
        if (x > 1) {
            if (x > 2) {
                if (x > 3) {
                    if (x > 4) {
                        if (x > 5) {
                            return x;
                        }
                    }
                }
            }
        }
    }
    return 0;
}
