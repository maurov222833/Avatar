// Lógica interactiva completa para Avatar Desktop GUI
function avatarFetch(url, options) {
    const opts = options ? Object.assign({}, options) : {};
    const headers = new Headers(opts.headers || {});
    if (window.AVATAR_HTTP_TOKEN) headers.set("X-Avatar-Token", window.AVATAR_HTTP_TOKEN);
    opts.headers = headers;
    return fetch(url, opts);
}

let attachedFileContent = "";
let monacoEditorInstance = null;

document.addEventListener("DOMContentLoaded", () => {
    loadConfig();
    loadProjects();
    setupEventListeners();
    initMonacoEditor();
});

function initMonacoEditor() {
    if (typeof require !== "undefined") {
        require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs' }});
        require(['vs/editor/editor.main'], function() {
            const container = document.getElementById('monaco-editor-container');
            if (container && !monacoEditorInstance) {
                monacoEditorInstance = monaco.editor.create(container, {
                    value: '# ⚡ LIVE CODE VIEWER DE AVATAR AI WORKSPACE\n# El código generado y modificado por Avatar aparecerá aquí en tiempo real...\n\ndef main():\n    print("¡Sistema Avatar operando en tiempo real con Monaco IDE!")\n\nif __name__ == "__main__":\n    main()\n',
                    language: 'python',
                    theme: 'vs-dark',
                    automaticLayout: true,
                    fontSize: 13,
                    minimap: { enabled: true }
                });
            }
        });
    }
}

function loadCodeIntoMonaco(codeText, language = "python", filename = "live_code.py") {
    const panel = document.getElementById("code-viewer-panel");
    if (panel.classList.contains("hidden")) {
        panel.classList.remove("hidden");
    }
    
    document.getElementById("code-viewer-filename").innerHTML = `<i class="fa-solid fa-code text-cyan-400"></i> ${filename}`;
    
    if (monacoEditorInstance) {
        monaco.editor.setModelLanguage(monacoEditorInstance.getModel(), language);
        monacoEditorInstance.setValue(codeText);
    }
}

function toggleCodeViewer() {
    const panel = document.getElementById("code-viewer-panel");
    panel.classList.toggle("hidden");
    if (monacoEditorInstance) {
        setTimeout(() => monacoEditorInstance.layout(), 100);
    }
}

function copyMonacoCode() {
    if (monacoEditorInstance) {
        const val = monacoEditorInstance.getValue();
        navigator.clipboard.writeText(val).then(() => {
            alert("✓ Código copiado al portapapeles desde Monaco Editor");
        });
    }
}

function setupEventListeners() {
    const userInput = document.getElementById("user-input");
    userInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
}

async function loadConfig() {
    try {
        const res = await avatarFetch("/api/config");
        if (res.ok) {
            const config = await res.json();
            const provider = config.default_provider || "gemini";
            document.getElementById("model-select").value = provider;
            updateHeaderBadge(provider);
            
            if (config.gemini) document.getElementById("gemini-key-input").value = config.gemini.api_key || "";
            if (config.openai) document.getElementById("openai-key-input").value = config.openai.api_key || "";
            if (config.groq) document.getElementById("groq-key-input").value = config.groq.api_key || "";
            if (config.github) document.getElementById("github-key-input").value = config.github.api_key || "";
            if (config.ollama) document.getElementById("ollama-url-input").value = config.ollama.url || "http://localhost:11434";
        }
    } catch (err) {
        console.error("Error al cargar configuración:", err);
    }
}

async function saveSettings() {
    const geminiKey = document.getElementById("gemini-key-input").value.trim();
    const openaiKey = document.getElementById("openai-key-input").value.trim();
    const groqKey = document.getElementById("groq-key-input").value.trim();
    const githubKey = document.getElementById("github-key-input").value.trim();
    const ollamaUrl = document.getElementById("ollama-url-input").value.trim();

    try {
        const res = await avatarFetch("/api/config/update", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                gemini_key: geminiKey,
                openai_key: openaiKey,
                groq_key: groqKey,
                github_key: githubKey,
                ollama_url: ollamaUrl
            })
        });

        if (res.ok) {
            const msgEl = document.getElementById("save-settings-msg");
            msgEl.classList.remove("hidden");
            setTimeout(() => msgEl.classList.add("hidden"), 3000);
            appendTerminalLog("[SYSTEM]: Configuración de API Keys y Servidores actualizada.");
            loadConfig();
        }
    } catch (err) {
        alert("Error al guardar la configuración: " + err);
    }
}

function updateHeaderBadge(provider) {
    const badge = document.getElementById("header-status-badge");
    const p = (provider || "gemini").toLowerCase();
    if (p === "gemini") {
        badge.className = "px-2 py-0.5 rounded bg-blue-950 text-cyan-400 border border-cyan-800 font-medium cursor-pointer";
        badge.innerHTML = '<i class="fa-solid fa-bolt"></i> Gemini 3.6';
    } else if (p === "groq") {
        badge.className = "px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-700 font-medium cursor-pointer";
        badge.innerHTML = '<i class="fa-solid fa-bolt-lightning"></i> Groq Cloud (14k Free)';
    } else if (p === "github") {
        badge.className = "px-2 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800 font-medium cursor-pointer";
        badge.innerHTML = '<i class="fa-brands fa-github"></i> GitHub Models (Free)';
    } else if (p === "openai") {
        badge.className = "px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-medium cursor-pointer";
        badge.innerHTML = '<i class="fa-solid fa-robot"></i> ChatGPT 4o';
    } else if (p === "lmstudio") {
        badge.className = "px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800 font-medium cursor-pointer";
        badge.innerHTML = '<i class="fa-solid fa-desktop"></i> LM Studio Local';
    } else {
        badge.className = "px-2 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-800 font-medium cursor-pointer";
        badge.innerHTML = '<i class="fa-solid fa-terminal"></i> Ollama Local';
    }
}

async function changeActiveModel() {
    const selectedProvider = document.getElementById("model-select").value;
    try {
        const res = await avatarFetch("/api/config/provider", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ provider: selectedProvider })
        });
        if (res.ok) {
            updateHeaderBadge(selectedProvider);
            appendTerminalLog(`[SYSTEM]: Motor de IA cambiado activamente a: ${selectedProvider.toUpperCase()}`);
        }
    } catch (err) {
        console.error("Error cambiando modelo:", err);
    }
}

function changeAgentMode() {
    const mode = document.getElementById("mode-select").value;
    appendTerminalLog(`[SYSTEM]: Modo de Agente cambiado a: ${mode === 'agent' ? 'MAIN AGENT' : 'LOCAL EXECUTOR'}`);
}

async function loadProjects() {
    try {
        const res = await avatarFetch("/api/projects");
        if (res.ok) {
            const data = await res.json();
            const listEl = document.getElementById("projects-list");
            listEl.innerHTML = "";
            (data.projects || ["PROYECTOS ANTIGRAVITY", "Avatar"]).forEach(proj => {
                const item = document.createElement("div");
                item.className = "px-2 py-1.5 rounded hover:bg-gray-800/60 text-gray-300 flex items-center space-x-2 cursor-pointer";
                item.onclick = () => selectProject(proj);
                item.innerHTML = `<i class="fa-solid fa-folder text-cyan-400"></i> <span>${proj}</span>`;
                listEl.appendChild(item);
            });
        }
    } catch (e) {
        console.log("No se pudieron cargar proyectos dinámicos");
    }
}

async function selectProject(name) {
    try {
        const res = await avatarFetch("/api/workspace/set", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project_name: name })
        });
        const data = await res.json();
        appendTerminalLog(`[WORKSPACE]: Proyecto activo seleccionado -> ${name}`);
        document.getElementById("user-input").value = `Analiza el proyecto '${name}' y dime su estructura.`;
    } catch (e) {
        console.error(e);
    }
}

function triggerFileUpload() {
    document.getElementById("file-input").click();
}

async function handleFileSelected(event) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
        const res = await avatarFetch("/api/attach", {
            method: "POST",
            body: formData
        });
        if (res.ok) {
            const data = await res.json();
            attachedFileContent = data.full_content;
            
            document.getElementById("attachment-preview").classList.remove("hidden");
            document.getElementById("attachment-filename").innerText = `📎 ${data.filename} (${data.full_content.length} bytes)`;
            appendTerminalLog(`[ATTACHMENT]: Archivo ${data.filename} cargado exitosamente.`);
        }
    } catch (err) {
        alert("Error al cargar archivo: " + err);
    }
}

function removeAttachment() {
    attachedFileContent = "";
    document.getElementById("attachment-preview").classList.add("hidden");
    appendTerminalLog("[ATTACHMENT]: Archivo adjunto removido.");
}

function toggleVoiceDictation() {
    const micBtn = document.getElementById("mic-btn");
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();
        recognition.lang = 'es-ES';
        
        micBtn.classList.add("text-red-500", "animate-pulse");
        appendTerminalLog("[VOICE]: Escuchando dictado por voz...");
        
        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            document.getElementById("user-input").value += " " + transcript;
            micBtn.classList.remove("text-red-500", "animate-pulse");
            appendTerminalLog(`[VOICE]: Transcripción -> ${transcript}`);
        };
        
        recognition.onerror = () => {
            micBtn.classList.remove("text-red-500", "animate-pulse");
        };

        recognition.start();
    } else {
        alert("Tu navegador o entorno de ejecución no soporta la API de reconocimiento de voz. Puedes escribir tu consulta directamente.");
    }
}

async function sendMessage() {
    const inputEl = document.getElementById("user-input");
    let message = inputEl.value.trim();
    
    if (attachedFileContent) {
        message += `\n\n[ARCHIVO ADJUNTO]:\n${attachedFileContent}`;
        removeAttachment();
    }

    if (!message) return;

    inputEl.value = "";
    
    // Ocultar mensaje de bienvenida inicial si está visible
    const welcomeMsg = document.getElementById("welcome-message");
    if (welcomeMsg) welcomeMsg.style.display = "none";

    appendUserMessage(message);
    const loadingId = appendLoadingBubble();

    try {
        const res = await avatarFetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: message })
        });

        removeBubble(loadingId);

        if (res.ok) {
            const data = await res.json();
            appendAvatarMessage(data.avatar_response, data.provider);
            appendTerminalLog(`[AVATAR ${data.provider.toUpperCase()}]: Procesado correctamente.`);
        } else {
            let errorText = "⚠️ Ocurrió un error al procesar tu solicitud.";
            try {
                const errData = await res.json();
                if (errData && errData.detail) {
                    errorText = `⚠️ Error en servidor (HTTP ${res.status}): ${errData.detail}`;
                } else if (errData && errData.avatar_response) {
                    errorText = errData.avatar_response;
                }
            } catch(e) {}
            appendAvatarMessage(errorText);
        }
    } catch (err) {
        removeBubble(loadingId);
        appendAvatarMessage("❌ Error de conexión con el backend de Avatar.");
        console.error("Error en sendMessage:", err);
    }
}

function appendUserMessage(text) {
    const container = document.getElementById("chat-container");
    const msgDiv = document.createElement("div");
    msgDiv.className = "flex justify-end mb-4";
    msgDiv.innerHTML = `
        <div class="max-w-2xl chat-bubble-user p-4 text-white text-sm shadow-lg">
            <div class="text-[10px] text-cyan-400 font-bold mb-1 flex items-center gap-1">
                <i class="fa-solid fa-user"></i> MAURO
            </div>
            <div>${escapeHtml(text)}</div>
        </div>
    `;
    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
}

function appendAvatarMessage(markdownText, provider = "gemini") {
    const container = document.getElementById("chat-container");
    const msgDiv = document.createElement("div");
    msgDiv.className = "flex justify-start mb-4";
    
    const parsedHtml = marked.parse(markdownText);
    const msgId = "msg-" + Date.now();
    
    msgDiv.innerHTML = `
        <div class="max-w-3xl chat-bubble-avatar p-5 text-gray-200 text-sm shadow-xl w-full relative">
            <div class="text-[11px] text-emerald-400 font-bold mb-2 flex items-center justify-between border-b border-gray-800 pb-2">
                <span class="flex items-center gap-1.5">
                    <i class="fa-solid fa-atom text-cyan-400"></i> AVATAR ENGINE (${provider.toUpperCase()})
                </span>
                <div class="flex items-center space-x-2">
                    <button onclick="copyMessageText('${msgId}')" class="px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 text-[10px] flex items-center gap-1 transition">
                        <i class="fa-regular fa-copy"></i> <span>Copiar</span>
                    </button>
                    <span class="text-[9px] text-gray-500 font-normal">Sovereign Antigravity Agent</span>
                </div>
            </div>
            <div id="${msgId}" class="prose prose-invert max-w-none leading-relaxed select-text">${parsedHtml}</div>
        </div>
    `;
    container.appendChild(msgDiv);
    
    // Resaltar código y añadir botón de inspección en Monaco Editor
    msgDiv.querySelectorAll("pre code").forEach((block, idx) => {
        hljs.highlightElement(block);
        
        const codeText = block.innerText;
        const langClass = Array.from(block.classList).find(c => c.startsWith("language-"));
        const lang = langClass ? langClass.replace("language-", "") : "python";
        
        const btn = document.createElement("button");
        btn.className = "mt-2 px-2.5 py-1 bg-cyan-950 hover:bg-cyan-900 border border-cyan-800 text-cyan-300 rounded text-[10px] font-mono flex items-center gap-1.5 transition";
        btn.innerHTML = `<i class="fa-solid fa-code"></i> Abrir en Monaco IDE`;
        btn.onclick = () => loadCodeIntoMonaco(codeText, lang, `generated_code_${idx + 1}.${lang === 'python' ? 'py' : lang}`);
        
        block.parentElement.appendChild(btn);
        
        // Auto-cargar en Monaco si es el primer bloque de código generado
        if (idx === 0) {
            loadCodeIntoMonaco(codeText, lang, `code_generated.${lang === 'python' ? 'py' : lang}`);
        }
    });

    container.scrollTop = container.scrollHeight;
}

function copyMessageText(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    
    const textToCopy = el.innerText || el.textContent;
    navigator.clipboard.writeText(textToCopy).then(() => {
        appendTerminalLog("[CLIPBOARD]: Mensaje de Avatar copiado al portapapeles exitosamente.");
        alert("✓ Mensaje copiado al portapapeles");
    }).catch(err => {
        // Fallback
        const textarea = document.createElement("textarea");
        textarea.value = textToCopy;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
        alert("✓ Mensaje copiado al portapapeles");
    });
}

function appendLoadingBubble() {
    const container = document.getElementById("chat-container");
    const id = "loading-" + Date.now();
    const msgDiv = document.createElement("div");
    msgDiv.id = id;
    msgDiv.className = "flex justify-start mb-4";
    msgDiv.innerHTML = `
        <div class="chat-bubble-avatar p-4 text-cyan-400 text-xs flex items-center space-x-2">
            <i class="fa-solid fa-circle-notch fa-spin text-sm"></i>
            <span>Avatar pensando y ejecutando...</span>
        </div>
    `;
    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
    return id;
}

function removeBubble(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function appendTerminalLog(text) {
    const term = document.getElementById("terminal-output");
    const line = document.createElement("div");
    line.innerText = text;
    term.appendChild(line);
    term.scrollTop = term.scrollHeight;
}

async function handleTerminalCommand(e) {
    if (e.key === "Enter") {
        const inputEl = document.getElementById("terminal-cmd-input");
        const cmd = inputEl.value.trim();
        if (!cmd) return;

        inputEl.value = "";
        appendTerminalLog(`PS b:\\PROYECTOS ANTIGRAVITY> ${cmd}`);

        try {
            const res = await avatarFetch("/api/terminal/execute", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ command: cmd })
            });
            if (res.ok) {
                const data = await res.json();
                appendTerminalLog(data.output);
            }
        } catch (err) {
            appendTerminalLog(`[Error ejecutando comando]: ${err}`);
        }
    }
}

function switchTerminalTab(tab) {
    const psBtn = document.getElementById("tab-powershell-btn");
    const logsBtn = document.getElementById("tab-logs-btn");

    if (tab === "powershell") {
        psBtn.className = "text-cyan-400 border-b-2 border-cyan-400 pb-0.5 flex items-center gap-1";
        logsBtn.className = "text-gray-500 hover:text-gray-300 pb-0.5 flex items-center gap-1";
        appendTerminalLog("[TERMINAL]: Vista de PowerShell activa.");
    } else {
        logsBtn.className = "text-cyan-400 border-b-2 border-cyan-400 pb-0.5 flex items-center gap-1";
        psBtn.className = "text-gray-500 hover:text-gray-300 pb-0.5 flex items-center gap-1";
        appendTerminalLog("[TERMINAL]: Vista de Logs de Agente activa.");
    }
}

function createNewConversation() {
    document.getElementById("chat-container").innerHTML = `
        <div id="welcome-message" class="max-w-3xl mx-auto text-center space-y-3 pt-6">
            <h1 class="text-3xl font-bold text-white tracking-tight">PROYECTOS ANTIGRAVITY</h1>
            <p class="text-sm text-gray-400">Nueva conversación iniciada con Avatar AI Agent.</p>
        </div>
    `;
    appendTerminalLog("[SYSTEM]: Nueva sesión de chat iniciada.");
}

function showHistoryDrawer() {
    alert("Historial de conversaciones cargado. Puedes hacer clic en cualquier sesión de la lista para reanudarla.");
}

function openTasksModal() {
    const modal = document.getElementById("tasks-modal");
    modal.classList.toggle("hidden");
    modal.classList.toggle("flex");
}

function toggleSettingsModal() {
    const modal = document.getElementById("settings-modal");
    modal.classList.toggle("hidden");
    modal.classList.toggle("flex");
}

function toggleSidebar() {
    const sb = document.getElementById("sidebar");
    sb.classList.toggle("hidden");
}

function toggleTerminal() {
    const term = document.getElementById("terminal-panel");
    term.classList.toggle("h-44");
    term.classList.toggle("h-8");
}

function showAppInfo() {
    alert("⚡ AVATAR AI - Sovereign Agent Workspace v1.0.0\nDesarrollado en b:\\PROYECTOS ANTIGRAVITY\\Avatar");
}

function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
