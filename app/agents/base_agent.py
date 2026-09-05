from abc import ABC, abstractmethod
from app.models.schemas import AgentContext, AgentOutput


class BaseAgent(ABC):
    name = "base_agent"

    @abstractmethod
    def run(self, ctx: AgentContext) -> AgentOutput:
        raise NotImplementedError
