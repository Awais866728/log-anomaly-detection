"""Turn a stream of parsed lines into closed windows, grouped the same way as in training.

- LineWindows: fixed windows of n lines in arrival order (BGL, as in bgl_features.make_windows)
- BlockWindows: one window per HDFS block (as in hdfs_features); a block is closed when no line for it has
  arrived for `idle` seconds of log time, or when the replay ends
- TimeWindows: fixed 1-minute windows by line time (live services, as in time_windows.make_time_windows)
"""

from collections import OrderedDict
from dataclasses import dataclass, field

MAX_LINES_KEPT = 50  # raw lines kept per window for the dashboard


@dataclass
class Window:
    source: str
    window_id: object
    events: list = field(default_factory=list)  # "E<cluster id>" per line, in order
    lines: list = field(default_factory=list)  # (stream id, raw line), first MAX_LINES_KEPT
    first_time: float = None  # log time of the first and last line (unix seconds)
    last_time: float = None
    last_received: float = None  # when the last line reached the stream (unix seconds)
    n_lines: int = 0
    labels: list = field(default_factory=list)  # replay only: true line/block labels, for display

    def add(self, event, line_id, raw, log_time, received, label=None):
        self.events.append(event)
        self.n_lines += 1
        if len(self.lines) < MAX_LINES_KEPT:
            self.lines.append((line_id, raw))
        if log_time is not None:
            self.first_time = log_time if self.first_time is None else self.first_time
            self.last_time = log_time
        self.last_received = received
        if label is not None:
            self.labels.append(label)


class LineWindows:
    def __init__(self, source, size=20, start_index=0):
        self.source, self.size, self.index = source, size, start_index
        self.current = Window(source, start_index)

    def add(self, event, line_id, raw, log_time, received, label=None):
        self.current.add(event, line_id, raw, log_time, received, label)
        if self.current.n_lines < self.size:
            return []
        closed, self.index = self.current, self.index + 1
        self.current = Window(self.source, self.index)
        return [closed]

    def tick(self, now):
        return []

    def flush(self):
        return []  # the last partial window is dropped, as in training


class BlockWindows:
    def __init__(self, source, idle=4 * 3600):
        self.source, self.idle = source, idle
        self.open = OrderedDict()  # block id -> Window, least recently updated first
        self.closed_ids = set()
        self.late_lines = 0  # lines for blocks that were already closed (ignored)

    def add_multi(self, event, blocks, line_id, raw, log_time, received, label=None):
        closed = self._close_idle(log_time)
        for block in blocks:
            if block in self.closed_ids:
                self.late_lines += 1
                continue
            window = self.open.pop(block, None) or Window(self.source, block)
            window.add(event, line_id, raw, log_time, received, label)
            self.open[block] = window
        return closed

    def _close_idle(self, log_time):
        closed = []
        while log_time is not None and self.open:
            block, window = next(iter(self.open.items()))
            if window.last_time is None or log_time - window.last_time <= self.idle:
                break
            closed.append(self.open.pop(block))
            self.closed_ids.add(block)
        return closed

    def tick(self, now):
        return []

    def flush(self):
        closed = list(self.open.values())
        self.closed_ids.update(self.open)
        self.open.clear()
        return closed


class TimeWindows:
    """started: when collection started (unix seconds); a window that began earlier is only partly collected
    and is dropped instead of scored."""

    def __init__(self, source, seconds=60, grace=5, started=None):
        self.source, self.seconds, self.grace = source, seconds, grace
        self.current = None
        self.started = started

    def _close(self):
        closed, self.current = self.current, None
        if self.started is not None and closed.window_id < self.started:
            return []
        return [closed]

    def add(self, event, line_id, raw, log_time, received, label=None):
        start = int(log_time // self.seconds * self.seconds)
        closed = []
        if self.current is not None and start > self.current.window_id:
            closed = self._close()
        if self.current is None or start < self.current.window_id:  # late line: keep it in the open window
            self.current = self.current or Window(self.source, start)
        self.current.add(event, line_id, raw, log_time, received, label)
        return closed

    def tick(self, now):
        """Close the open window once its minute is over (plus a few seconds for late lines)."""
        if self.current is not None and now > self.current.window_id + self.seconds + self.grace:
            return self._close()
        return []

    def flush(self):
        return self._close() if self.current else []
