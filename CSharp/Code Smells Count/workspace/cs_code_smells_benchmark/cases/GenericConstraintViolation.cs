namespace Cases;

public class GenericConstraintViolation
{
    public void Process<T>() where T : class, new()
    {
        _ = new T();
    }
}
