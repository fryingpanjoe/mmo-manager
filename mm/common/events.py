import pickle


def serialize_event_to_string(event):
    return pickle.dumps(event)


def serialize_event_from_string(string):
    return pickle.loads(string)


class ClientEvent(object):
    def __init__(self, client_id, event):
        self.client_id = client_id
        self.event = event


class ClientConnectedEvent(object):
    def __init__(self, client_id):
        self.client_id = client_id


class ClientDisconnectedEvent(object):
    def __init__(self, client_id):
        self.client_id = client_id


class EnterGameEvent(object):
    def __init__(self, width, height, actor_states):
        self.width = width
        self.height = height
        self.actor_states = actor_states


class DeltaStateEvent(object):
    def __init__(self, actor_states):
        self.actor_states = actor_states


class ActorSpawnedEvent(object):
    def __init__(self, actor_state):
        self.actor_state = actor_state


class ActorDiedEvent(object):
    def __init__(self, actor_id):
        self.actor_id = actor_id


class AttackEvent(object):
    def __init__(self, attacker_id, victim_id, damage):
        self.attacker_id = attacker_id
        self.victim_id = victim_id
        self.damage = damage


class HealEvent(object):
    def __init__(self, actor_id, heal):
        self.actor_id = actor_id
        self.heal = heal


class LootEvent(object):
    def __init__(self, actor_id, loot):
        self.actor_id = actor_id
        self.loot = loot


class SetTargetEvent(object):
    def __init__(self, actor_id, target_id, previous_target_id=None):
        self.actor_id = actor_id
        self.target_id = target_id
        self.previous_target_id = previous_target_id


class PlayerActionSpawnMobEvent(object):
    def __init__(self, actor_type, pos):
        self.actor_type = actor_type
        self.pos = pos


ALL_GAME_EVENT_TYPES = [
    ActorSpawnedEvent, ActorDiedEvent, AttackEvent, HealEvent, LootEvent,
    SetTargetEvent]

ALL_SERVER_EVENT_TYPES = [
    ClientEvent, ClientConnectedEvent, ClientDisconnectedEvent]

ALL_PLAYER_EVENT_TYPES = [PlayerActionSpawnMobEvent]

ALL_EVENT_TYPES = \
    ALL_GAME_EVENT_TYPES + \
    ALL_SERVER_EVENT_TYPES + \
    ALL_PLAYER_EVENT_TYPES + \
    [EnterGameEvent, DeltaStateEvent]


class EventDistributor(object):
    def __init__(self):
        self.handler_id = 100
        self.handlers = {}
        self.queue = []

    def add_handler(self, handler, event_types):
        if not isinstance(event_types, (list, tuple)):
            event_types = [event_types]

        self.handler_id += 1
        handler_id = self.handler_id
        self.handlers[handler_id] = (handler, event_types)
        return self.handler_id

    def remove_handler(self, handler_id):
        if handler_id in self.handlers:
            del self.handlers[handler_id]

    def update(self):
        q = self.queue
        self.queue = []
        for event in q:
            self.send(event)

    def send(self, event):
        for (handler, event_types) in self.handlers.values():
            if type(event) in event_types:
                handler(event)

    def post(self, event):
        self.queue.append(event)
