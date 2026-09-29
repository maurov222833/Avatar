import sys
import os

# Asegurar importación de módulos de Avatar
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.prompt import Prompt
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from core.orchestrator import AvatarOrchestrator

def print_banner(console, orchestrator):
    cfg = orchestrator.llm.config
    provider = cfg.get("default_provider", "gemini").upper()
    
    if provider == "GEMINI":
        provider_badge = "[bold white on blue] 🌐 GOOGLE GEMINI 3.5 [/bold white on blue]"
    elif provider in ["OPENAI", "CHATGPT"]:
        provider_badge = "[bold white on green] 🤖 OPENAI CHATGPT-4O [/bold white on green]"
    else:
        provider_badge = "[bold black on yellow] 💻 OLLAMA LOCAL [/bold black on yellow]"

    banner_text = r"""
 [bold cyan]   ___  _   ___ _____ _   ___   [/bold cyan]
 [bold cyan]  / _ \| | / / /_   _/_\ | _ \  [/bold cyan]  [bold yellow]Sovereign Agentic System[/bold yellow]
 [bold cyan] / /_\ \ |/ / /_\ | |/ _ \|   /  [/bold cyan]  [bold green]Version 1.0.0 (Antigravity Interactive TUI)[/bold green]
 [bold cyan]/_/   \_\___/_/   \_/_/ \_\_|_\\ [/bold cyan]  [dim]100% Privado | Multi-Modelo | Local Shell[/dim]
""" + f"""
 🧠 Motor Activo: {provider_badge}   🛡️ Seguridad: [bold green]Confirmación Humana ACTIVADA[/bold green]
    """
    console.print(Panel(banner_text, border_style="cyan", expand=False))

def show_help(console):
    table = Table(title="📌 Comandos Interactivosa de Avatar Terminal", border_style="dim")
    table.add_column("Comando / Slash", style="bold cyan")
    table.add_column("Descripción / Función", style="white")
    
    table.add_row("/model [gemini|openai|ollama]", "Cambia al instante el cerebro de IA (Gemini, ChatGPT u Ollama).")
    table.add_row("/status", "Muestra el informe detallado del estado del sistema.")
    table.add_row("/clear", "Limpia la pantalla y redibuja el panel principal.")
    table.add_row("/help", "Muestra esta guía de comandos.")
    table.add_row("/exit", "Cierra la sesión de Avatar.")
    
    console.print(table)

def show_status(console, orchestrator):
    cfg = orchestrator.llm.config
    provider = cfg.get("default_provider", "gemini").upper()
    
    table = Table(title="⚙️ Estado del Sistema Avatar AI", border_style="green")
    table.add_column("Parámetro", style="bold yellow")
    table.add_column("Valor Configurado", style="white")

    table.add_row("Proyecto", cfg.get("project_name", "Avatar AI Engine"))
    table.add_row("Proveedor Actual", f"[bold cyan]{provider}[/bold cyan]")
    table.add_row("Modelo Gemini", cfg.get("gemini", {}).get("model", "gemini-3.5-flash-lite"))
    table.add_row("Modelo OpenAI", cfg.get("openai", {}).get("model", "gpt-4o-mini"))
    table.add_row("Modelo Ollama Local", cfg.get("ollama", {}).get("model", "qwen2.5-coder:1.5b"))
    table.add_row("Seguridad", "🛡️ Modo Confirmación Humana ACTIVADO")
    table.add_row("Directorio de Trabajo", "b:\\PROYECTOS ANTIGRAVITY\\Avatar")

    console.print(table)

def switch_model_menu(console, orchestrator, arg: str = ""):
    arg = arg.strip().lower()
    cfg = orchestrator.llm.config

    if arg in ["gemini", "1"]:
        new_provider = "gemini"
    elif arg in ["groq", "2"]:
        new_provider = "groq"
    elif arg in ["github", "3"]:
        new_provider = "github"
    elif arg in ["openai", "chatgpt", "4"]:
        new_provider = "openai"
    elif arg in ["lmstudio", "5"]:
        new_provider = "lmstudio"
    elif arg in ["ollama", "local", "6"]:
        new_provider = "ollama"
    else:
        console.print("\n[bold yellow]🧠 SELECCIÓN DE MOTOR DE INTELIGENCIA ARTIFICIAL:[/bold yellow]")
        console.print(" 1. [cyan]Google Gemini[/cyan] (Pago / Tier Gratuito)")
        console.print(" 2. [bold cyan]Groq Cloud[/bold cyan] (⚡ 14,400 req/día GRATIS - Ultra Rápido)")
        console.print(" 3. [bold purple]GitHub Models[/bold purple] (🐙 GPT-4o / Llama 70B GRATIS)")
        console.print(" 4. [green]OpenAI ChatGPT-4o[/green] (Respaldo de Alta Capacidad)")
        console.print(" 5. [bold yellow]LM Studio Local[/bold yellow] (🖥️ 100% Offline con GUI)")
        console.print(" 6. [yellow]Ollama Local[/yellow] (💻 100% Offline CLI)")
        
        choice = Prompt.ask("\n👉 Selecciona una opción (1-6)", choices=["1", "2", "3", "4", "5", "6", "gemini", "groq", "github", "openai", "lmstudio", "ollama"], default="1")
        mapping = {"1": "gemini", "2": "groq", "3": "github", "4": "openai", "5": "lmstudio", "6": "ollama"}
        new_provider = mapping.get(choice, choice)

    # Actualizar configuración dinámicamente
    cfg["default_provider"] = new_provider
    import json
    from core.paths import config_path as resolve_config_path
    path = resolve_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    orchestrator.llm.config_path = path

    orchestrator.llm.load_config()
    console.print(f"\n✅ [bold green]Motor de IA cambiado exitosamente a: {new_provider.upper()}[/bold green]\n")

def tty_exec_approver(act_type: str, args: dict) -> bool:
    """Ask the operator at the terminal before an approval-gated act runs. Default is no."""
    command = args.get("command") or args.get("params") or ""
    print("\n🛡️  [AVATAR] Se requiere tu aprobación para ejecutar un comando en tu PC:")
    print(f"   {act_type}: {command}")
    try:
        answer = input("👉 ¿Autorizas esta ejecución? (s/N) > ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("s", "si", "sí", "y", "yes")


def run_cli():
    # Habilitar Virtual Terminal Processing (ANSI TrueColor) en consolas de Windows
    if os.name == "nt":
        import ctypes
        try:
            kernel32 = ctypes.windll.kernel32
            # Activar banderas de salida VT y colores ANSI
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass

    console = Console(force_terminal=True, color_system="truecolor") if RICH_AVAILABLE else None
    orchestrator = AvatarOrchestrator()
    try:
        interactive = sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        interactive = False
    if interactive and orchestrator.chokepoint is not None:
        orchestrator.chokepoint.approver = tty_exec_approver

    if RICH_AVAILABLE:
        os.system("cls" if os.name == "nt" else "clear")
        print_banner(console, orchestrator)
        console.print("[dim cyan]Escribe tu consulta en lenguaje natural o cambia de modelo con /model (gemini | openai | ollama)[/dim cyan]\n")
    else:
        print("=" * 65)
        print(" 🤖 AVATAR AGENTIC TERMINAL ")
        print("=" * 65)

    while True:
        try:
            cfg = orchestrator.llm.config
            provider = cfg.get("default_provider", "gemini").lower()
            
            if provider == "gemini":
                badge = "[blue]Gemini 3.5[/blue]"
            elif provider == "openai":
                badge = "[green]ChatGPT 4o[/green]"
            else:
                badge = "[yellow]Ollama Local[/yellow]"

            if RICH_AVAILABLE:
                prompt_label = f"[{badge}] [bold cyan]Avatar[/bold cyan] [bold green]❯[/bold green] "
                user_input = Prompt.ask(prompt_label).strip()
            else:
                user_input = input(f"[{provider.upper()}] Avatar ❯ ").strip()

            if not user_input:
                continue

            # Procesamiento de comandos Slash
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd in ["/exit", "exit", "salir", "quit"]:
                if RICH_AVAILABLE:
                    console.print("\n[bold yellow]👋 Sesión finalizada. Tu Agente Avatar queda en espera.[/bold yellow]\n")
                else:
                    print("\n👋 Sesión finalizada.")
                break
            elif cmd in ["/model", "/modelo", "/provider"]:
                if RICH_AVAILABLE:
                    switch_model_menu(console, orchestrator, arg)
                    print_banner(console, orchestrator)
                else:
                    print("Usa /model gemini, /model openai o /model ollama")
                continue
            elif cmd == "/help":
                if RICH_AVAILABLE:
                    show_help(console)
                else:
                    print("Comandos disponibles: /model, /status, /help, /clear, /exit")
                continue
            elif cmd == "/status":
                if RICH_AVAILABLE:
                    show_status(console, orchestrator)
                else:
                    print("Estado del sistema activo.")
                continue
            elif cmd in ["/clear", "cls", "clear"]:
                os.system("cls" if os.name == "nt" else "clear")
                if RICH_AVAILABLE:
                    print_banner(console, orchestrator)
                continue

            # Procesamiento de la orden con el Orquestador
            if RICH_AVAILABLE:
                console.print(Panel(user_input, title="👤 [bold cyan]MAURO[/bold cyan]", border_style="bold blue"))
                console.print(f"[dim yellow]🧠 Avatar [{provider.upper()}] pensando y ejecutando...[/dim yellow]")
                response = orchestrator.process_user_input(user_input)
                console.print(Panel(Markdown(response), title=f"🤖 [bold green]AVATAR ENGINE ({provider.upper()})[/bold green]", subtitle="[dim cyan]Sovereign Antigravity Agent[/dim cyan]", border_style="bold green"))
            else:
                print(f"\n[Mauro]: {user_input}")
                print("\n[Avatar pensando...]")
                response = orchestrator.process_user_input(user_input)
                print(f"\n🤖 [AVATAR]:\n{response}")

        except KeyboardInterrupt:
            if RICH_AVAILABLE:
                console.print("\n[bold red]\n👋 Sesión cancelada.[/bold red]")
            break
        except Exception as e:
            if RICH_AVAILABLE:
                console.print(f"[bold red]❌ Error en Terminal:[/bold red] {str(e)}")
            else:
                print(f"Error: {e}")

if __name__ == "__main__":
    run_cli()
