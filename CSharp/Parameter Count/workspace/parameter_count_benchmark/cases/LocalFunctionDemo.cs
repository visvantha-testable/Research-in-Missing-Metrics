namespace Cases;

public class LocalFunctionDemo
{
    public int Run(int x)
    {
        int LocalWithMany(int a, int b, int c, int d, int e, int f, int g)
        {
            return a + b + c + d + e + f + g + x;
        }

        return LocalWithMany(1, 2, 3, 4, 5, 6, 7);
    }
}
