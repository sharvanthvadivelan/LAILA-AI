from abc import ABC, abstractmethod


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    @abstractmethod
    async def models(self): ...
    @abstractmethod
    async def show(self, model): ...
    @abstractmethod
    async def complete(self, model, messages, options, tools=None): ...
    @abstractmethod
    def stream(self, model, messages, options, tools=None): ...
    @abstractmethod
    async def embed(self, model, texts): ...
