import asyncio
from typing import Any

import httpx

class ComfyUIClient:
    def __init__(self, base_url: str= "http://127.0.0.1:8000", timeout: float = 300.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=timeout)

    async def wait_for_comfyui(self, timeout: float = 120, interval: float = 0.5) -> None:
        start = asyncio.get_running_loop().time()

        while True:
            try:
                response = await self.client.get(f"{self.base_url}/system_stats")

                if response.status_code == 200:
                    print("ComfyUI is ready.")
                    return

            except Exception:
                pass

            if asyncio.get_running_loop().time() - start >= timeout:
                raise TimeoutError("ComfyUI failed to become ready.")

            await asyncio.sleep(interval)

    async def queue_prompt(self, workflow: dict[str, Any]) -> str:
        response = await self.client.post(f"{self.base_url}/prompt",
                                         json={
                                             "prompt": workflow
                                         })

        if response.status_code != 200:
            print("\n===== COMFYUI ERROR =====")
            print(response.text)
            print("=========================\n")

        response.raise_for_status()

        data = response.json()
        return data.get("prompt_id")

    async def get_history(
        self,
        prompt_id: str,
    ) -> dict[str, Any]:

        response = await self.client.get(
            f"{self.base_url}/history/{prompt_id}"
        )

        response.raise_for_status()

        return response.json()


    async def wait_for_completion(
        self,
        prompt_id: str,
        poll_interval: float = 1.0,
    ) -> dict[str, Any]:

        while True:

            history = await self.get_history(
                prompt_id
            )

            if prompt_id in history:

                return history[prompt_id]

            await asyncio.sleep(
                poll_interval
            )

    async def get_system_stats(self):
        response = await self.client.get(
            f"{self.base_url}/system_stats"
        )

        response.raise_for_status()
        return response.json()

    async def download_image(
            self,
            filename: str,
            subfolder: str = "",
            image_type: str = "output",
    ) -> bytes:

        response = await self.client.get(
            f"{self.base_url}/view",
            params={
                "filename": filename,
                "subfolder": subfolder,
                "type": image_type,
            },
        )

        response.raise_for_status()

        return response.content

    async def close(self):

        await self.client.aclose()