namespace Cases;

public static class ExtensionMethodDemo
{
    public static int SumWithParams(this int seed, int a, int b, params int[] values)
    {
        return seed + a + b + values.Sum();
    }
}
