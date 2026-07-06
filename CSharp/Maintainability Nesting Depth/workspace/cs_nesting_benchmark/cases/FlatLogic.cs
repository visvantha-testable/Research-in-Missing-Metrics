namespace Cases;

public class FlatLogic
{
    public int Add(int a, int b)
    {
        return a + b;
    }

    public string FormatName(string first, string last)
    {
        var full = $"{first} {last}";
        return full.Trim();
    }
}
