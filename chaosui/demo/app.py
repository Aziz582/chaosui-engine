"""
FastAPI vulnerable playground server for ChaosUI demonstration.
"""

from __future__ import annotations
import asyncio
import os
import uuid
from typing import List, Dict, Any
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="ChaosUI Vulnerable Playground")

orders_db: List[Dict[str, Any]] = []


class CheckoutRequest(BaseModel):
    item: str
    amount: float
    email: str


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    static_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(static_file, "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/checkout")
async def process_checkout(req: CheckoutRequest):
    # Simulate processing latency (e.g. 250ms payment gateway delay)
    await asyncio.sleep(0.25)
    order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"
    order = {
        "order_id": order_id,
        "item": req.item,
        "amount": req.amount,
        "email": req.email,
    }
    orders_db.append(order)
    return JSONResponse(
        {
            "status": "success",
            "order_id": order_id,
            "total_orders": len(orders_db),
            "item": req.item,
        }
    )


@app.get("/api/orders")
async def get_orders():
    return {"orders": orders_db, "count": len(orders_db)}


def run_demo_server(host: str = "127.0.0.1", port: int = 8080):
    """Starts the demo playground server."""
    uvicorn.run(app, host=host, port=port, log_level="warning")
