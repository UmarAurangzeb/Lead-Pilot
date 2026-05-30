"""
OutreachAgent — sends personalised emails via MCP Gmail (SMTP fallback).

MCP path: connects to a local Gmail MCP server and invokes the send_email tool.
If the MCP server is unavailable, falls back transparently to SMTP (utils/smtp.py).
"""
from __future__ import annotations

import logging
import os

import memory
from a2a.types import AgentCard, AgentSkill, Artifact, Task, TaskResult
from agents.base import A2AAgent
from helpers import normalize_email_list
from templates import build_email, select_portfolio
from utils.smtp import send_email

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MCP Gmail client (graceful fallback when server not running)
# ---------------------------------------------------------------------------

class _MCPGmailClient:
    """
    Wraps the Gmail MCP server's send_email tool.

    The MCP server must be running at the address in MCP_GMAIL_URL (default
    http://localhost:3100).  If it's unreachable this client marks itself
    unavailable and the OutreachAgent falls back to SMTP automatically.
    """

    def __init__(self) -> None:
        self._url = os.getenv("MCP_GMAIL_URL", "http://localhost:3100")
        self._available = self._probe()

    def _probe(self) -> bool:
        try:
            import httpx
            r = httpx.get(f"{self._url}/.well-known/agent.json", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    @property
    def available(self) -> bool:
        return self._available

    def send(self, *, to: str, subject: str, html_body: str) -> bool:
        if not self._available:
            return False
        try:
            import httpx
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client

            async def _send():
                async with streamablehttp_client(f"{self._url}/mcp") as (r, w, _):
                    async with ClientSession(r, w) as session:
                        await session.initialize()
                        await session.call_tool(
                            "send_email",
                            {"to": to, "subject": subject, "body": html_body, "mimeType": "text/html"},
                        )

            import asyncio
            asyncio.get_event_loop().run_until_complete(_send())
            return True
        except Exception as exc:
            log.warning("MCP Gmail send failed (%s) — falling back to SMTP", exc)
            self._available = False
            return False


_mcp = _MCPGmailClient()


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class OutreachAgent(A2AAgent):
    """Sends niche-personalised emails with inline portfolio screenshots."""

    @property
    def agent_card(self) -> AgentCard:
        return AgentCard(
            name="OutreachAgent",
            description=(
                "Sends personalised outreach emails to qualified leads. "
                "Selects the most relevant portfolio project per niche and embeds screenshots."
            ),
            version="1.0.0",
            skills=[
                AgentSkill(
                    id="send-outreach",
                    name="Send Outreach",
                    description="Build and send a niche-personalised HTML email to a lead.",
                    input_modes=["data"],
                    output_modes=["data"],
                )
            ],
        )

    def process(self, task: Task) -> TaskResult:
        data = task.message.get_data()
        high_quality: list[dict] = data.get("high_quality", [])
        niche: str = data.get("niche", "local businesses")
        dry_run: bool = os.getenv("OUTREACH_DRY_RUN", "false").lower() in ("1", "true", "yes")

        portfolio = select_portfolio(niche)
        log.info("Outreach using portfolio: %s for niche '%s'", portfolio["name"], niche)

        log_entries: list[str] = []

        for lead in high_quality:
            recipients = normalize_email_list(lead.get("emails"))
            if not recipients:
                log_entries.append(f"skip:no-email:{lead.get('title')}")
                continue

            title = lead.get("title") or "your business"
            address = lead.get("address") or ""
            # crude location: last comma-separated segment of address
            location = address.split(",")[-1].strip() if address else ""
            primary = recipients[0]
            cc = recipients[1:] if len(recipients) > 1 else None

            subject, html_body = build_email(
                business_name=title,
                niche=niche,
                location=location,
                portfolio=portfolio,
            )

            if dry_run:
                log_entries.append(f"dry-run:{title}:{primary}:template={portfolio['name']}")
                continue

            sent = False
            if _mcp.available:
                sent = _mcp.send(to=primary, subject=subject, html_body=html_body)
                if sent:
                    log_entries.append(f"sent(mcp):{title}:{primary}")

            if not sent:
                try:
                    plain = (
                        f"Hi,\n\nI came across {title} and wanted to reach out.\n\n"
                        f"I'm Umar, a software engineer and a freelance developer. I recently built {portfolio['name']} "
                        f"({portfolio['url']}) — {portfolio['desc']}\n\n"
                        f"Happy to chat if improving your digital setup is on your radar.\n\n"
                        f"Best,\nUmar Aurangzeb\numaraurangzeb03@gmail.com"
                    )
                    send_email(
                        to_addrs=primary,
                        subject=subject,
                        body=plain,
                        html_body=html_body,
                        cc=cc,
                    )
                    log_entries.append(f"sent(smtp):{title}:{primary}")
                    sent = True
                except Exception as exc:
                    log_entries.append(f"error:{title}:{primary}:{exc}")

            if sent:
                try:
                    memory.update_status(lead["lead_hash"], "CONTACTED")
                except Exception:
                    pass

        return TaskResult(
            task_id=task.id,
            status="completed",
            artifacts=[Artifact(name="emails", data=log_entries)],
        )
