struct Widget;
struct LargeStruct;

extern int add(int a, int b);
extern int const_demo(int seed);
extern int duplicate_expr(int a, int b);
extern int call_helper(void);
extern int known_condition(int value);
extern int trigger_passed_by_value(struct LargeStruct input);
extern int shadow_demo(int outer);
extern int unread_demo(void);
extern int public_api(void);
extern int use_widget(struct Widget *w);
extern int scope_demo(int n);

int benchmark_runner(void) {
    struct Widget w;
    struct LargeStruct ls;
    int total = 0;

    total += add(1, 2);
    total += const_demo(1);
    total += duplicate_expr(1, 1);
    total += call_helper();
    total += known_condition(3);
    total += trigger_passed_by_value(ls);
    total += shadow_demo(1);
    total += unread_demo();
    total += public_api();
    total += use_widget(&w);
    total += scope_demo(5);
    return total;
}
