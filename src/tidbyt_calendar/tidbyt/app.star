# Tidbyt Calendar tile. 64x32, tom-thumb (6px tall) -> 5 rows fill 30px.
#
# Each row: "MM/DD:" in a fixed-width box (stays put, DATE accent), then a Marquee
# holding "HH:MM" (TIME accent) + the title (white) that scrolls when it overflows.
# Rows scroll independently. All-day events have no time. Fewer than 5 events ->
# remaining rows blank. A "message" (e.g. "No Events", "Calendar unavailable") is
# shown centered instead of the list.
#
# Param (positional key=value): data = JSON
#   {"events": [{"date": "MM/DD", "time": "HH:MM" | "", "title": "..."}, ...],  # 0..5
#    "message": null | "..."}
load("render.star", "render")
load("encoding/json.star", "json")

WHITE = "#fff"
DATE_COLOR = "#ff9e3d"  # warm amber
TIME_COLOR = "#46c8ff"  # cyan
FONT = "tom-thumb"
ROW_H = 6
ROWS = 5
DATE_INK = 22  # inked px width of "MM/DD:" in tom-thumb (digits are fixed-width)
TITLE_W = 64 - DATE_INK  # marquee viewport width, butted against the colon


def _row(ev):
    # Lead with a space so the scroll content starts separated from the colon
    # ("MM/DD: title"); the space simply rides to the end as the marquee loops.
    scroll = []
    if ev.get("time"):
        scroll.append(render.Text(content = " " + ev["time"] + " ", font = FONT, color = TIME_COLOR))
        scroll.append(render.Text(content = ev["title"], font = FONT, color = WHITE))
    else:
        scroll.append(render.Text(content = " " + ev["title"], font = FONT, color = WHITE))

    # Left-align the date (so its first digit isn't clipped) and overlay the
    # marquee starting at the colon's inked edge — the date widget's 2px trailing
    # advance is blank, so the overlap is invisible and the spacing stays tight.
    return render.Stack(
        children = [
            render.Text(content = ev["date"] + ":", font = FONT, color = DATE_COLOR),
            render.Padding(
                pad = (DATE_INK, 0, 0, 0),
                child = render.Marquee(width = TITLE_W, child = render.Row(children = scroll)),
            ),
        ],
    )


def _blank():
    return render.Box(width = 64, height = ROW_H)


def _message(text):
    return render.Root(
        child = render.Box(
            width = 64,
            height = 32,
            child = render.WrappedText(
                content = text,
                font = FONT,
                color = WHITE,
                width = 64,
                align = "center",
            ),
        ),
    )


def main(config):
    data = json.decode(config.get("data", "{}"))

    message = data.get("message")
    if message:
        return _message(message)

    events = data.get("events", [])
    rows = []
    for i in range(ROWS):
        rows.append(_row(events[i]) if i < len(events) else _blank())

    return render.Root(
        child = render.Column(children = rows),
    )
