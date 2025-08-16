from yandex_cloud_ml_sdk import YCloudML
from typing import Optional


class YandexGPT:
    def __init__(self, folder_id: str, api_key: str, model: str = "yandexgpt-lite", version: str = "rc"):
        self.folder_id = folder_id
        self.api_key = api_key
        self.sdk = YCloudML(
            folder_id=folder_id,
            auth=api_key
        )
        self.model = self.sdk.models.completions(
            model,
            model_version=version
        ).configure(temperature=0.5)

    def complete(self, prompt: str) -> str:
        try:
            response = self.model.run(prompt)
            # print(response)
            return response.alternatives[0].text
        except Exception as e:
            raise RuntimeError(f"YandexGPT request failed: {e}")