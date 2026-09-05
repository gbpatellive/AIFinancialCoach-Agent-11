from app.agents.base_agent import BaseAgent
from app.models.schemas import AgentOutput


class ComplianceGuardAgent(BaseAgent):
    name = "compliance_guard"

    def run(self, ctx):
        return AgentOutput(
            agent_name=self.name,
            summary="Educational guidance only; not legal/tax/investment advice.",
            details={
                "disclaimer": "Consult licensed professionals for regulated advice.",
                "region": ctx.profile.region,
                "global_note": "Rules vary by country.",
            },
            confidence=0.99,
        )
