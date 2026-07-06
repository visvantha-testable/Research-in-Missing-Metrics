package cases;

public class CyclomaticComplexityDemo {
    public int complexBranches(int value) {
        int result = 0;
        if (value > 0) { result += 1; }
        if (value > 1) { result += 1; }
        if (value > 2) { result += 1; }
        if (value > 3) { result += 1; }
        if (value > 4) { result += 1; }
        if (value > 5) { result += 1; }
        if (value > 6) { result += 1; }
        if (value > 7) { result += 1; }
        if (value > 8) { result += 1; }
        if (value > 9) { result += 1; }
        if (value > 10) { result += 1; }
        if (value > 11) { result += 1; }
        return result;
    }
}
