create table setting
(
    id              serial
        primary key,
    name            text not null
        unique,
    selected_groups text
);

alter table setting
    owner to postgres;

INSERT INTO public.setting (id, name, selected_groups) VALUES (88, 'combined_training', '["group1", "math", "computer"]');
INSERT INTO public.setting (id, name, selected_groups) VALUES (86, 'edit_choose', '[]');
INSERT INTO public.setting (id, name, selected_groups) VALUES (99, 'index_top', '["group1"]');
