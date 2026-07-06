struct Widget {
    int id;
    int unused_field;
};

int use_widget(struct Widget *w) {
    w->id = 1;
    return w->id;
}
