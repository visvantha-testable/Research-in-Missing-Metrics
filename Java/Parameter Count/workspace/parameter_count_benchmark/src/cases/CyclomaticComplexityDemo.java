package cases;

public class CyclomaticComplexityDemo {
    public int complex(int value) {
        if (value > 0) return 1;
        if (value > 1) return 2;
        if (value > 2) return 3;
        if (value > 3) return 4;
        if (value > 4) return 5;
        if (value > 5) return 6;
        if (value > 6) return 7;
        if (value > 7) return 8;
        if (value > 8) return 9;
        if (value > 9) return 10;
        if (value > 10) return 11;
        return 0;
    }
}
