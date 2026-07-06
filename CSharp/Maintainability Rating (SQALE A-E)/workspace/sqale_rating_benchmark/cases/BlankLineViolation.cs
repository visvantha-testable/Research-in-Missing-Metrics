namespace Cases;

public class BlankLineViolation
{
    public int First()
    {
        return 1;
    }
    public int Second()
    {
        // Missing blank line before this comment triggers SA1515 in some contexts.
        return 2;
    }
}
