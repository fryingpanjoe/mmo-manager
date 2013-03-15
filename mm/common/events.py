

class ActorSpawnedEvent(object):
    def __init__(self, actor_id, actor_type, pos):
        self.actor_id = actor_id
        self.actor_type = actor_type
        self.pos = pos


class ActorKilledEvent(object):
    def __init__(self, victim_id):
        self.victim_id = victim_id


class AttackEvent(object):
    def __init__(self, attacker_id, victim_id, damage):
        self.attacker_id = attacker_id
        self.victim_id = victim_id
        self.damage = damage


class Distributor(object):
    def __init__(self):
        self.handler_id = 100
        self.handlers = {}
        self.queue = []

    def add_listener(self, handler, event_types):
        self.handler_id += 1
        handler_id = self.handler_id
        self.handlers[handler_id] = (handler, event_types)
        return self.handler_id

    def remove_listener(self, handler_id):
        if handler_id in self.handlers:
            del self.handlers[handler_id]

    def update(self):
        for event in self.queue:
            self.send(event)
        self.queue = []

    def send(self, event):
        for (handler, event_types) in self.handlers.itervalues():
            if type(event) in event_types:
                handler(event)

    def post(self, event):
        self.queue.append(event)
