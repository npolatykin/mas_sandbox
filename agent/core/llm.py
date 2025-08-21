from yandex_cloud_ml_sdk import YCloudML
from typing import Optional
from .logger import logger


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
        
        # Логируем инициализацию YandexGPT
        logger.info(f"YandexGPT инициализирован", "LLM", {
            "model": model,
            "version": version,
            "folder_id": folder_id[:8] + "..." if folder_id else None
        })

    def complete(self, prompt: str) -> str:
        try:
            # Логируем начало запроса
            logger.debug(f"Отправляю запрос к YandexGPT", "LLM", {"prompt_length": len(prompt)})
            
            response = self.model.run(prompt)
            
            # Логируем успешный ответ с токенами
            response_text = response.alternatives[0].text
            
            # Логируем с детальной информацией о токенах
            logger.log_llm(response, "yandexgpt-lite")
            
            logger.debug(f"Получен ответ от YandexGPT: {response_text}", "LLM", {"response": response_text})
            
            return response_text
            
        except Exception as e:
            # Логируем ошибку
            logger.error(f"Ошибка YandexGPT: {str(e)}", "LLM", {"prompt_length": len(prompt)})
            raise RuntimeError(f"YandexGPT request failed: {e}")