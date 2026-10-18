/* Exercise private menu routines without an X server. Unused UI sections are
   discarded at link time; the stubs below reject unexpected UI dependencies. */
#include <glib.h>
#include <string.h>

static gsize supplied;
static GIOStatus short_reads(GIOChannel *channel, gchar *buf, gsize count,
                            gsize *bytes, GError **error)
{
    (void)channel;
    (void)error;
    *bytes = MIN(count, supplied ? 4096 : 4095);
    if (supplied >= 1024 * 1024) {
        *bytes = 0;
        return G_IO_STATUS_AGAIN;
    }
    memset(buf, 'x', *bytes);
    supplied += *bytes;
    return G_IO_STATUS_NORMAL;
}

#define g_io_channel_read_chars short_reads
#include "openbox/menu.c"
#undef g_io_channel_read_chars

GList *menu_frame_visible;
void RrImageUnref(RrImage *image) { g_assert(image == NULL); }
void actions_act_unref(ObActionsAct *action) { g_assert(action == NULL); }
void menu_frame_refresh(ObMenu *menu) { g_assert_not_reached(); }

static void labels(void)
{
    static const struct {
        const gchar *input, *output;
        gboolean allow;
        gunichar key;
        guint position;
        gboolean explicit_key;
    } cases[] = {
        {"_File", "File", TRUE, 'f', 0, TRUE},
        {"a__b", "a_b", TRUE, 'a', 0, FALSE},
        {"__A_B__C", "_AB__C", TRUE, 'b', 2, TRUE},
        {"Exit_", "Exit", TRUE, 0, 0, FALSE},
        {"___", "_", TRUE, 0, 0, FALSE},
        {"_File", "_File", FALSE, 'f', 1, FALSE},
        {"a__b", "a_b", FALSE, 'a', 0, FALSE},
        {"é_A", "éA", TRUE, 'a', 2, TRUE},
        {"_é__A", "_é__A", TRUE, 0, 0, FALSE},
        {"", "", TRUE, 0, 0, FALSE}
    };
    guint n;
    for (n = 0; n < G_N_ELEMENTS(cases); ++n) {
        gchar *out;
        guint pos;
        gboolean explicit_key;
        gunichar key = parse_shortcut(cases[n].input, cases[n].allow,
                                     &out, &pos, &explicit_key);
        g_assert_cmpstr(out, ==, cases[n].output);
        g_assert_cmpuint(key, ==, cases[n].key);
        g_assert_cmpuint(pos, ==, cases[n].position);
        g_assert_cmpint(explicit_key, ==, cases[n].explicit_key);
        g_free(out);
    }
    {
        gchar *label = g_strnfill(400000, '_'), *out;
        guint pos;
        gboolean explicit_key;
        gint64 start = g_get_monotonic_time();
        parse_shortcut(label, TRUE, &out, &pos, &explicit_key);
        g_assert_cmpuint(strlen(out), ==, 200000);
        g_print("400 KB escaped label: %.3f ms\n",
                (g_get_monotonic_time() - start) / 1000.0);
        g_free(out);
        g_free(label);
    }
}

static void entries(void)
{
    ObMenu menu = {0}, more = {0};
    ObMenuEntry *first, *middle, *last;
    gint n;
    gint64 start;
    menu.more_menu = &more;
    first = menu_add_normal(&menu, 1, "_First", NULL, TRUE);
    middle = menu_add_submenu(&menu, 2, "child");
    last = menu_add_separator(&menu, 3, "Last");
    menu_entry_remove(middle);
    g_assert(menu.entries->next->data == last);
    menu_entry_remove(last);
    g_assert(menu.entries_tail == menu.entries);
    menu_add_separator(&menu, 4, "Replacement");
    menu_entry_remove(first);
    g_assert(more.entries == menu.entries);
    g_assert(menu.entries->prev == NULL);
    menu_clear_entries(&menu);
    g_assert(menu.entries == NULL && menu.entries_tail == NULL);
    g_assert(more.entries == NULL);
    start = g_get_monotonic_time();
    for (n = 0; n < 40000; ++n)
        menu_add_separator(&menu, n, "entry");
    g_print("40000 menu entries: %.3f ms\n",
            (g_get_monotonic_time() - start) / 1000.0);
    n = 0;
    for (GList *it = menu.entries; it; it = it->next, ++n) {
        g_assert_cmpint(((ObMenuEntry*)it->data)->id, ==, n);
        if (it->next) g_assert(it->next->prev == it);
        else g_assert(menu.entries_tail == it);
    }
    g_assert_cmpint(n, ==, 40000);
    menu_clear_entries(&menu);
    first = menu_add_separator(&menu, 1, NULL);
    menu_entry_remove(first);
    g_assert(menu.entries_tail == NULL && more.entries == NULL);
}

int main(void)
{
    ObMenu menu = {0};
    labels();
    entries();
    menu.pipe_output = g_string_new(NULL);
    for (guint i = 0; i < 2; ++i) {
        supplied = 0;
        g_assert(menu_pipe_read(NULL, i ? G_IO_HUP : G_IO_IN, &menu));
        g_assert_cmpuint(supplied, ==, 65536);
    }
    g_string_free(menu.pipe_output, TRUE);
    g_print("PASS: shortcuts, entry lifetime/order, short-read dispatch limits\n");
    return 0;
}
