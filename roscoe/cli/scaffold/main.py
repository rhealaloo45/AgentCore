"""Entry point for __PROJECT_NAME__. Run: python main.py"""

from roscoe import AgentRunner

from tools.my_tools import TOOLS

agent = AgentRunner.from_config("agent_config.yaml", tools=TOOLS)

if __name__ == "__main__":
    result = agent.run("What's the weather in London?")
    print("OUTPUT:", result.output)
    print("STATUS:", result.status)
    print("TOKENS:", result.total_tokens)
    if result.status == "error":
        print("ERROR :", result.error)
