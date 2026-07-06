namespace Cases;

public class LoopNesting
{
    public int NestedLoops(int[] values)
    {
        var total = 0;
        foreach (var item in values)
        {
            if (item > 0)
            {
                for (var i = 0; i < values.Length; i++)
                {
                    if (values[i] > 10)
                    {
                        for (var j = 0; j < values.Length; j++)
                        {
                            if (values[j] > 20)
                            {
                                total += values[j];
                            }
                        }
                    }
                }
            }
        }

        return total;
    }
}
