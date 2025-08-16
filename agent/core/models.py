from typing import TypedDict, Annotated, Dict, List


class UserData(TypedDict):
    user_id: str


class State(TypedDict):
    messages: Annotated[List[str], "history"]
    user_data: Annotated[UserData, "user_data"]
    stage: Annotated[str, "stage"]
    message_from_user: Annotated[List[str], "message_from_user"]
    message_to_user: Annotated[List[str], "message_to_user"]
