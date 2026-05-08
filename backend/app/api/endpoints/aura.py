"""
Aura AI Companion — Backend router.
Provides RAG-powered chat using live system state as context.
Uses rule-based NLP first; falls back to LLM if API key is configured.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────
class AuraChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None


class AuraChatResponse(BaseModel):
    reply: str
    intent: Optional[str] = None
    data: Optional[dict] = None


# ── System Context Builder ────────────────────────────────────────────────────
async def _build_system_context(db: AsyncSession) -> dict:
    """Fetch live system snapshot for RAG injection."""
    try:
        from sqlalchemy import select, func, text
        from app.db.models import CloudResource, HealingAction, EventLog

        # Resource counts
        total = await db.scalar(select(func.count()).select_from(CloudResource))
        critical = await db.scalar(
            select(func.count()).select_from(CloudResource)
            .where(CloudResource.cpu_usage > 80)
        )

        # Recent healing actions
        healing_rows = await db.execute(
            select(HealingAction)
            .order_by(HealingAction.created_at.desc())
            .limit(5)
        )
        healing_list = healing_rows.scalars().all()

        # Provider distribution
        provider_rows = await db.execute(
            select(CloudResource.provider, func.count().label("cnt"))
            .group_by(CloudResource.provider)
        )
        providers = {r.provider: r.cnt for r in provider_rows}

        return {
            "total_resources": total or 0,
            "critical_count": critical or 0,
            "providers": providers,
            "healing_total": len(healing_list),
            "recent_healing": [
                {
                    "action": h.action_type,
                    "resource": h.resource_name,
                    "status": h.status,
                    "time": h.created_at.isoformat() if h.created_at else None,
                }
                for h in healing_list
            ],
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.warning(f"Context build failed: {e}")
        return {"error": str(e), "total_resources": 0, "critical_count": 0}


# ── Rule-Based NLP Engine ─────────────────────────────────────────────────────
def _rule_based_response(message: str, ctx: dict) -> Optional[str]:
    """
    Fast rule-based responses for common queries — no LLM latency.
    Returns None if no rule matches (fallback to LLM or generic response).
    """
    msg = message.lower()
    total = ctx.get("total_resources", 0)
    critical = ctx.get("critical_count", 0)
    providers = ctx.get("providers", {})
    healing = ctx.get("recent_healing", [])
    healing_total = ctx.get("healing_total", 0)

    # System health query
    if any(k in msg for k in ["health", "status", "overview", "summary", "how is"]):
        health_pct = max(0, 100 - (critical / max(total, 1)) * 100) if total else 100
        status = "🟢 **Optimal**" if health_pct > 80 else "🟡 **Degraded**" if health_pct > 50 else "🔴 **Critical**"
        provider_str = ", ".join([f"**{p.upper()}**: {c}" for p, c in providers.items()]) or "none connected"
        return (
            f"**System Health Summary**\n\n"
            f"Health Score: {status} ({health_pct:.0f}%)\n"
            f"Total Resources: **{total}** | Critical: **{critical}**\n"
            f"Providers: {provider_str}\n"
            f"Autonomous Heals: **{healing_total}** executed\n\n"
            f"{'⚠️ Immediate attention required for ' + str(critical) + ' critical resource(s).' if critical > 0 else '✅ All systems operating within normal parameters.'}"
        )

    # Degraded/critical resources
    if any(k in msg for k in ["degraded", "critical", "failing", "down", "unhealthy", "problem"]):
        if critical == 0:
            return "✅ Good news! No resources are currently in a **critical** or degraded state. All systems are operating normally."
        return (
            f"⚠️ **{critical} resource(s)** are currently in a critical state (CPU > 80%).\n\n"
            f"Navigate to the **Dashboard** or **Prediction** page to view them. "
            f"You can trigger auto-healing from the **Healing** page, or ask me: *\"trigger healing on [resource name]\"*."
        )

    # Last healing action
    if any(k in msg for k in ["last heal", "last action", "what did", "recent heal", "explain heal", "healing action"]):
        if not healing:
            return "No healing actions have been recorded yet. The autonomous healer will act when risk scores exceed safe thresholds."
        last = healing[0]
        return (
            f"**Last Autonomous Action** (via AI)\n\n"
            f"Action: `{last['action'].upper()}`\n"
            f"Target: **{last['resource']}**\n"
            f"Status: `{last['status']}`\n"
            f"Time: {last['time'] or 'Unknown'}\n\n"
            f"This action was triggered because the resource's risk score exceeded the configured threshold, "
            f"prompting the healing engine to execute a `{last['action']}` to restore service stability."
        )

    # CPU / hotspots
    if any(k in msg for k in ["cpu", "hotspot", "high load", "compute", "processor"]):
        return (
            f"**CPU Hotspot Analysis**\n\n"
            f"Currently **{critical}** resource(s) are running above 80% CPU utilization.\n"
            f"Check the **Dashboard** for the Node Inventory table — resources with red CPU bars are your hotspots.\n\n"
            f"The AI healing engine will automatically trigger `scale_up` when CPU exceeds 90%."
        )

    # Provider info
    if any(k in msg for k in ["aws", "azure", "gcp", "google", "provider", "cloud"]):
        if not providers:
            return "No cloud providers are currently connected. Go to **Cloud Connect** to add your AWS, GCP, or Azure credentials."
        lines = [f"- **{p.upper()}**: {c} resource(s)" for p, c in providers.items()]
        return f"**Connected Cloud Providers**\n\n" + "\n".join(lines) + "\n\nAll providers are being actively monitored."

    # Graph / topology
    if any(k in msg for k in ["graph", "topology", "dependency", "architecture", "map"]):
        return (
            "The **Dependency Graph** visualizes relationships between your cloud resources in real-time. "
            "Navigate to `/graph` to explore it. Nodes are colored by health: 🟢 green = healthy, 🔴 red = critical.\n\n"
            "Click any node to inspect its telemetry and trigger investigations."
        )

    # Help
    if any(k in msg for k in ["help", "what can you", "what do you", "commands", "abilities"]):
        return (
            "**What I can do for you:**\n\n"
            "- 🔍 *Show me degraded resources* → list critical infrastructure\n"
            "- 💊 *Explain the last healing action* → describe AI decisions\n"
            "- 📊 *System health summary* → full health overview\n"
            "- 🔥 *CPU hotspots* → identify high-load nodes\n"
            "- ☁️ *Provider status* → cloud connection details\n"
            "- 🗺️ *Topology info* → dependency graph guidance\n\n"
            "I have **real-time access** to your infrastructure state!"
        )

    return None  # No rule matched


# ── LLM Fallback ─────────────────────────────────────────────────────────────
def _llm_response(message: str, ctx: dict) -> str:
    """
    Attempt LLM response. Falls back to a smart generic if no API key.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")

    if api_key and os.getenv("GEMINI_API_KEY"):
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            system_prompt = f"""You are Aura, an AI assistant for an autonomous multi-cloud healing platform.
You have real-time access to the following infrastructure state:
- Total resources: {ctx.get('total_resources', 0)}
- Critical resources: {ctx.get('critical_count', 0)}
- Providers: {ctx.get('providers', {})}
- Recent healing actions: {ctx.get('recent_healing', [])}

Be concise, helpful, and technical. Use **bold** for emphasis. Keep responses under 150 words.
User asks: {message}"""
            resp = model.generate_content(system_prompt)
            return resp.text
        except Exception as e:
            logger.warning(f"Gemini API failed: {e}")
            error_msg = str(e)

    # Generic intelligent fallback
    fallback_msg = (
        f"I understand you're asking about: *\"{message}\"*\n\n"
        f"Based on the current system state (**{ctx.get('total_resources', 0)}** resources monitored, "
        f"**{ctx.get('critical_count', 0)}** critical), I recommend checking the **Dashboard** and **Healing** pages for detailed insights.\n\n"
    )
    
    if api_key and 'error_msg' in locals():
        fallback_msg += f"⚠️ **Aura Hub reported an issue:** `{error_msg}`\n\n"
    
    fallback_msg += "💡 *Tip: Configure `GEMINI_API_KEY` for enhanced AI responses.*"
    return fallback_msg



# ── Routes ────────────────────────────────────────────────────────────────────
@router.get("/context")
async def get_context(db: AsyncSession = Depends(get_db)):
    """Return live system snapshot for Aura RAG."""
    ctx = await _build_system_context(db)
    return ctx


@router.post("/chat", response_model=AuraChatResponse)
async def chat(req: AuraChatRequest, db: AsyncSession = Depends(get_db)):
    """Process a user message and return Aura's intelligent response."""
    # Refresh context if not provided
    ctx = req.context or await _build_system_context(db)

    # Try rule-based first (fast, no latency)
    reply = _rule_based_response(req.message, ctx)

    intent = "rule_based"
    if reply is None:
        reply = _llm_response(req.message, ctx)
        intent = "llm"

    return AuraChatResponse(reply=reply, intent=intent, data=ctx)


@router.post("/command")
async def command(req: AuraChatRequest, db: AsyncSession = Depends(get_db)):
    """Parse natural language command and return structured action."""
    msg = req.message.lower()
    action = None

    if "heal" in msg or "fix" in msg or "restart" in msg:
        action = {"type": "trigger_healing", "redirect": "/healing"}
    elif "scan" in msg or "discover" in msg:
        action = {"type": "trigger_scan", "redirect": "/connect"}
    elif "graph" in msg or "topology" in msg:
        action = {"type": "open_graph", "redirect": "/graph"}
    elif "predict" in msg or "risk" in msg:
        action = {"type": "open_prediction", "redirect": "/prediction"}
    elif "war room" in msg or "terminal" in msg:
        action = {"type": "open_warroom", "redirect": "/war-room"}

    return {"message": req.message, "action": action}
