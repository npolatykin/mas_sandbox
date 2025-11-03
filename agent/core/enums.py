from enum import IntEnum, StrEnum

class StageEnum(StrEnum):
    ROUTER_NODE = "router"
    END = "__end__"
    GENERATE_NODE = "generate_node"
    OTHER_NODE = "other_node"
    TASK_CREATE_NODE = "task_create"
    TASK_UPDATE_NODE = "task_update"
    TASK_DELETE_NODE = "task_delete"
    TASK_SEARCH_NODE = "task_search"

class PhraseOwnerEnum(StrEnum):
    HUMAN = "human"
    AI = "ai"