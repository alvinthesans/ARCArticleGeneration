from pathlib import Path


class PromptConstruct:
    def __init__(self, prompt_directory: str = "D:\ProgramData\ARCArticleGeneration\prompts"):
        self.prompt_directory = Path(prompt_directory)

    def getDefaultPrompt(self, file_name = "caruosel.txt"):
        path  = (
            self.prompt_directory / file_name
        )

        if not path.exists():
            raise FileNotFoundError(f"Prompt file {file_name} not found")

        with open(path, "r", encoding="utf-8") as f:
            prompt = f.read()

        return prompt
