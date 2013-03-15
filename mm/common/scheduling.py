import random


class Scheduler(object):
    def __init__(self):
        self.timers = []

    def post(self, func, delay):
        self.timers.append((Timer(delay), func, False))

    def periodic(self, func, period):
        self.timers.append((Timer(period, False), func, True))

    def update(self, frame_time):
        for (timer, func, periodic) in self.timers:
            timer.update(frame_time)
            if timer.is_expired_then_reset():
                func()
                if not periodic:
                    self.timers.remove((timer, func, periodic))


class Timer(object):
    def __init__(self, duration, do_reset=True):
        if isinstance(duration, (list, tuple)):
            self.min_duration = duration[0]
            self.max_duration = duration[1]
        else:
            self.min_duration = duration
            self.max_duration = None

        if do_reset:
            self.reset()
        else:
            self.time_left = 0

    def update(self, frame_time):
        self.time_left -= frame_time
        return not self.expired()

    def expired(self):
        return self.time_left <= 0

    def reset(self, time_left=None):
        if time_left:
            self.time_left = time_left
        else:
            if self.max_duration:
                self.time_left = random.uniform(
                    self.min_duration, self.max_duration)
            else:
                self.time_left = self.min_duration

    def fforward(self):
        self.time_left = 0

    def is_expired_then_reset(self):
        if self.expired():
            self.reset()
            return True
        else:
            return False
