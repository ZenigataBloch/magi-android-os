from fastapi import FastAPI
from pydantic import BaseModel

from core.controller import run_magi
from core.memory import save_decision
from core.magi import create_magi_agents


app = FastAPI(
    title="MAGI-OS API",
    version="1.0"
)


# verranno caricati da main in seguito
agents = create_magi_agents()

class MAGIRequest(BaseModel):

    prompt: str



@app.get("/")
def root():

    return {
        "system": "MAGI-OS",
        "status": "ONLINE"
    }



@app.post("/analyze")
async def analyze(
    request: MAGIRequest
):

    results = await run_magi(
        request.prompt,
        agents
    )


    decision = results["decision"]


    save_decision(
        request.prompt,
        decision
    )


    return {

        "prompt": request.prompt,

        "decision": decision

    }