import pytest
import importlib

def test_mcp_metadata_discovery():
    from backend import plugins
    names = {m["name"] for m in plugins.MCP_METADATA}
    assert "nmap" in names
    assert "gobuster" in names
    for m in plugins.MCP_METADATA:
        assert "name" in m
        assert "category" in m
        assert "description" in m
        assert "requires_approval" in m

@pytest.mark.asyncio
async def test_nmap_plugin_command_construction():
    from plugins.network import nmap_plugin
    info = await nmap_plugin.run_tool(target="127.0.0.1", options="-F")
    assert info["command"] == "nmap -F 127.0.0.1"
    assert "127.0.0.1" in info["approve_message"]
    assert "-F" in info["approve_message"]
    assert info["risk"] is not None
    assert info["docker"] is True

@pytest.mark.asyncio
async def test_nmap_plugin_default_target():
    from plugins.network import nmap_plugin
    info = await nmap_plugin.run_tool(target="scanme.nmap.org")
    assert "scanme.nmap.org" in info["command"]

@pytest.mark.asyncio
async def test_gobuster_plugin_installed_path(monkeypatch):
    from plugins.web import gobuster_plugin
    monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/gobuster")
    info = await gobuster_plugin.run_tool(target="http://example.com")
    assert info["command"] == "gobuster dir -u http://example.com -w /usr/share/wordlists/dirb/common.txt -q -t 10"
    assert "Enumerate directories" in info["approve_message"]
    assert "apt-get" not in info["command"]

@pytest.mark.asyncio
async def test_gobuster_plugin_not_installed_prepends_install(monkeypatch):
    from plugins.web import gobuster_plugin
    monkeypatch.setattr("shutil.which", lambda x: None)
    info = await gobuster_plugin.run_tool(target="http://example.com")
    assert "apt-get install -y gobuster" in info["command"]
    assert "gobuster dir -u http://example.com" in info["command"]
    assert "not installed" in info["approve_message"].lower()

@pytest.mark.asyncio
async def test_gobuster_plugin_custom_wordlist(monkeypatch):
    from plugins.web import gobuster_plugin
    monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/gobuster")
    info = await gobuster_plugin.run_tool(target="http://example.com", wordlist="/custom/list.txt")
    assert "/custom/list.txt" in info["command"]

@pytest.mark.asyncio
async def test_gobuster_plugin_risk_and_docker():
    from plugins.web import gobuster_plugin
    import shutil
    orig = shutil.which
    try:
        info = await gobuster_plugin.run_tool(target="http://example.com")
        assert info["risk"] == "medium (active scanning)"
        assert info["docker"] is True
    finally:
        pass
