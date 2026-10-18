/* Run only on the private display started by async-pipemenu.py. */
#include "obt/display.h"
#include "obt/prop.h"
#include "obt/internal.h"
#include <X11/Xatom.h>
#include <string.h>

static void set_words(Window window, Atom property, guint count)
{
    gulong chunk[32768];
    guint written = 0, i;
    XDeleteProperty(obt_display, window, property);
    while (written < count) {
        guint n = MIN(count - written, G_N_ELEMENTS(chunk));
        for (i = 0; i < n; ++i) chunk[i] = written + i;
        XChangeProperty(obt_display, window, property, XA_CARDINAL, 32,
                        PropModeAppend, (guchar*)chunk, n);
        written += n;
    }
}

int main(void)
{
    Window window;
    Atom ordinary, icon;
    guint count;
    guint32 *words;
    gchar *text, *large;
    const guchar title[] = {'A', 0xc3, 0xa9}; /* No trailing NUL. */

    /* Avoid accidentally running this on the user's live display. */
    g_assert_cmpstr(g_getenv("OPENBOX_PRIVATE_TEST_DISPLAY"), ==, "1");
    obt_display = XOpenDisplay(NULL);
    g_assert(obt_display);
    obt_prop_startup();
    window = XCreateSimpleWindow(obt_display, DefaultRootWindow(obt_display),
                                 0, 0, 10, 10, 0, 0, 0);
    ordinary = XInternAtom(obt_display, "_OPENBOX_TEST_ARRAY", False);
    icon = OBT_PROP_ATOM(NET_WM_ICON);
    for (guint i = 0; i < 2; ++i) {
        Atom property = i ? icon : ordinary;
        guint limit = (i ? 16 : 1) * 1024 * 1024 / 4;
        set_words(window, property, limit);
        g_assert(obt_prop_get_array32(window, property, XA_CARDINAL, &words, &count));
        g_assert_cmpuint(count, ==, limit);
        g_assert_cmpuint(words[count-1], ==, limit-1);
        g_free(words);
        if (!i) {
            g_assert(obt_prop_get_array32(window, property, AnyPropertyType,
                                          &words, &count));
            g_assert_cmpuint(count, ==, limit);
            g_free(words);
        }
        {
            gulong extra = 1;
            XChangeProperty(obt_display, window, property, XA_CARDINAL, 32,
                            PropModeAppend, (guchar*)&extra, 1);
        }
        words = NULL;
        g_assert(!obt_prop_get_array32(window, property, XA_CARDINAL, &words, &count));
        g_assert(words == NULL);
    }
    XChangeProperty(obt_display, window, ordinary, XA_STRING, 8,
                    PropModeReplace, title, sizeof(title));
    g_assert(!obt_prop_get_array32(window, ordinary, XA_CARDINAL, &words, &count));
    XChangeProperty(obt_display, window, ordinary, OBT_PROP_ATOM(UTF8_STRING), 8,
                    PropModeReplace, title, sizeof(title));
    g_assert(obt_prop_get_text(window, ordinary, OBT_PROP_TEXT_UTF8_STRING, &text));
    g_assert_cmpstr(text, ==, "Aé");
    g_free(text);
    g_assert(!obt_prop_get_text(window, ordinary, OBT_PROP_TEXT_STRING, &text));
    large = g_strnfill(65536, 'a');
    XDeleteProperty(obt_display, window, ordinary);
    for (guint i = 0; i < 16; ++i)
        XChangeProperty(obt_display, window, ordinary, OBT_PROP_ATOM(UTF8_STRING),
                        8, PropModeAppend, (guchar*)large, 65536);
    g_assert(obt_prop_get_text(window, ordinary, OBT_PROP_TEXT_UTF8_STRING, &text));
    g_assert_cmpuint(strlen(text), ==, 1024 * 1024);
    g_free(text);
    XChangeProperty(obt_display, window, ordinary, OBT_PROP_ATOM(UTF8_STRING),
                    8, PropModeAppend, (guchar*)large, 1);
    g_assert(!obt_prop_get_text(window, ordinary, OBT_PROP_TEXT_UTF8_STRING, &text));
    g_free(large);
    XDestroyWindow(obt_display, window);
    XCloseDisplay(obt_display);
    g_print("PASS: array/icon/text limits, exact boundaries, types, non-NUL UTF-8\n");
    return 0;
}
