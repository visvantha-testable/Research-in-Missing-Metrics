namespace Cases;

public class DepthThree
{
    public int ThreeLevels(int a, int b, int c)
    {
        if (a > 0)
        {
            if (b > 0)
            {
                if (c > 0)
                {
                    return a + b + c;
                }
            }
        }

        return 0;
    }
}
