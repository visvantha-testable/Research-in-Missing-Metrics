package cases;

public class DepthFourViolation {
    public int overThreshold(int x, int y, int z, int w) {
        if (x > 0) {
            if (y > 0) {
                if (z > 0) {
                    if (w > 0) {
                        return x + y + z + w;
                    }
                }
            }
        }
        return 0;
    }
}
