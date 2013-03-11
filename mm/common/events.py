

class EvActorSpawned(object):
    def __init__(self, actor_id, actor_type, pos):
        self.actor_id = actor_id
        self.actor_type = actor_type
        self.pos = pos


class EvActorKilled(object):
    def __init__(self, victim_id):
        self.victim_id = victim_id


class EvAttack(object):
    def __init__(self, attacker_id, victim_id, damage):
        self.attacker_id = attacker_id
        self.victim_id = victim_id
        self.damage = damage
