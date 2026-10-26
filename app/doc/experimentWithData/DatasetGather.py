import asyncio

from app.core.engine import OllamaClient
from app.visualQA.semanticQA.semantic_qa import GenerateTestRecord

ollamaClient = OllamaClient()
record_generator = GenerateTestRecord(ollamaClient)

asyncio.run(record_generator.main())