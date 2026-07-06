package cases;

public class DepthThree {
    public int atThreshold(int x, int y, int z) {
        if (x > y) {
            if (y > z) {
                if (z == x) {
                    return 1;
                }
            }
        }
        return 0;
    }
}
