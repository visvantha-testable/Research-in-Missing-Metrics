package cases;

public class NestedControlDemo {
    public int nestedExample(int x) {
        if (x > 0) {
            if (x > 1) {
                if (x > 2) {
                    return x;
                }
            }
        }
        return 0;
    }
}
