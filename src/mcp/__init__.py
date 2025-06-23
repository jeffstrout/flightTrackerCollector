"""
MCP (Model Context Protocol) module for Flight Tracker Collector.

This module provides MCP server functionality integrated with the flight tracker,
allowing AI assistants to interact with live flight data through structured tools.
"""

from .server import MCPServer

__all__ = ["MCPServer"]