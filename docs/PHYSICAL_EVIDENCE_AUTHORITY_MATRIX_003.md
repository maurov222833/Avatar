# AVATAR AI — PHYSICAL EVIDENCE AUTHORITY MATRIX (003)

## 1. MATRIZ DE AUTORIDAD DE EVIDENCIA POR CAPACIDAD

| Capacidad ID | Nombre de Capacidad | Evidencias Requeridas | Anclaje Físico Demostrado | Autoridad Evaluadora | Estado Actual | Limitaciones Conocidas |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CAP_STATE_ENGINE** | StateEngine Persistence | `FILESYSTEM_EVIDENCE`, `DATABASE_EVIDENCE` | Sí (Archivo DB en disco + SQLite WAL) | `PhysicalFactVerifier` + Registry | `VERIFIED` / `PARTIAL` según ejecuciones | Requiere archivo DB real |
| **CAP_CHECKPOINT_RESUME** | Checkpoint and Resume Engine | `FILESYSTEM_EVIDENCE`, `DATABASE_EVIDENCE` | Sí (Archivos checkpoint JSON + DB) | `PhysicalFactVerifier` + Registry | `VERIFIED` / `PARTIAL` según ejecuciones | Requiere verificación de hash |
| **CAP_DESKTOP_VISION** | Desktop Control & Local Vision OCR | `SCREEN_EVIDENCE`, `WINDOW_EVIDENCE` | Sí (Capturas PNG + Rectángulos de ventana) | `PhysicalFactVerifier` + Registry | `PARTIAL` (Requiere ambas evidencias) | Falta módulo OCR live integrado |
| **CAP_PLAYWRIGHT_BROWSER** | Playwright Browser Automation | `BROWSER_EVIDENCE`, `SCREEN_EVIDENCE` | Sí (Instancia Chromium + DOM observation) | `PhysicalFactVerifier` + Registry | `PARTIAL` (Requiere ambas evidencias) | Dependencia de binarios Playwright |
| **CAP_WHATSAPP_AUTO_REPLY** | WhatsApp Integration & Auto-Reply | `COMMUNICATION_EVIDENCE`, `NETWORK_EVIDENCE` | Sí (Respuesta Network/WS + Log de comunicación) | `PhysicalFactVerifier` + Registry | `PARTIAL` (Requiere ambas evidencias) | Bloqueado sin sesión activa QR |

---

## 2. REGLA EPISTÉMICA DE TRANSICIÓN

Para cualquier capacidad $C$:

$$\text{Status}(C) = \begin{cases} 
\text{VERIFIED} & \text{si } \text{RequiredTypes}(C) \subseteq \{t \mid \exists e \in \text{Ev}(C): e.\text{type} = t \land e.\text{physical} = \text{True} \land e.\text{verified} = \text{True}\} \\
\text{PARTIAL} & \text{si } \text{Ev}(C) \neq \emptyset \text{ y no cumple el criterio anterior} \\
\text{NOT\_IMPLEMENTED} & \text{si } \text{Ev}(C) = \emptyset
\end{cases}$$

Esta matriz de autoridad rige el comportamiento determinista de Avatar AI contra la auto-certificación por afirmaciones de texto o simulaciones no autorizadas.
