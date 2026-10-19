# Local launchers

Scripts for running the agency on your own machine. Run them from anywhere; each one
finds the repo root itself. First-time setup is `install.sh` / `install.ps1` at the repo root.

| Task | macOS / Linux | Windows |
|---|---|---|
| Start proxy + Ollama + tunnel | `./scripts/local/start_server.sh` | `.\scripts\local\start_server.ps1` |
| Stop everything | `./scripts/local/stop_server.sh` | `.\scripts\local\stop_server.ps1` |
| Proxy only | `./scripts/local/run_proxy.sh` | `.\scripts\local\start_proxy_only.ps1` |
| Print the tunnel URL | `./scripts/local/get_tunnel_url.sh` | `.\scripts\local\get_tunnel_url.ps1` |
| Claude Code against the proxy | `./scripts/local/launch-claude-code.sh` | `.\scripts\local\launch-claude-code.ps1` |
| Full local agency (backend + UI) | `./scripts/quickstart.sh` | `scripts\local\Start-Local-Agency.cmd` |
| Start on login | `./scripts/local/setup_autostart_macos.sh` | `.\scripts\local\setup_autostart.ps1` |
| Permanent ngrok URL | `python scripts/local/setup_ngrok.py --token …` | same |
