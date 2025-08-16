from enum import IntEnum, StrEnum

class StageEnum(StrEnum):
    ROUTER_NODE = "router"
    END = "__end__"
    GENERATE_NODE = "generate_node"
    OTHER_NODE = "other_node"
    # continue

class PhraseOwnerEnum(StrEnum):
    HUMAN = "human"
    AI = "ai"