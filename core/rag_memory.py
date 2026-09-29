import os
import json
from typing import List, Dict, Any, Optional
from core.state_db import StateEngine
from core.paths import memory_dir as default_memory_dir

class RAGMemory:
    """
    MÓDULO 2: Memoria Persistente, Base de Conocimiento Acumulativa y RAG para Avatar AI.
    Integrado con StateEngine (SQLite WAL) como backend persistente autoritativo de estado operacional.
    Preserva el 100% de la API pública existente y mantiene compatibilidad con history.json/context.json.
    """
    def __init__(self, memory_dir: Optional[str] = None, state_db: Optional[StateEngine] = None):
        self.memory_dir = memory_dir if memory_dir is not None else default_memory_dir()
        os.makedirs(self.memory_dir, exist_ok=True)
        self.history_file = os.path.join(self.memory_dir, "history.json")
        self.context_file = os.path.join(self.memory_dir, "context.json")
        self.knowledge_file = os.path.join(self.memory_dir, "knowledge_base.json")
        
        # Backend Autoritativo StateEngine (SQLite WAL)
        if state_db is not None:
            self.state_db = state_db
        else:
            db_path = os.path.join(self.memory_dir, "state_engine.db")
            self.state_db = StateEngine(db_path=db_path)
            
        self._migrate_legacy_json_if_needed()

    def _migrate_legacy_json_if_needed(self):
        """Migración segura y transparente de history.json y context.json hacia SQLite WAL."""
        try:
            # Migrar historial si SQLite está vacío
            existing_db_history = self.state_db.load_history()
            if not existing_db_history and os.path.exists(self.history_file):
                with open(self.history_file, "r", encoding="utf-8") as f:
                    history_data = json.load(f)
                    if isinstance(history_data, list):
                        for entry in history_data:
                            if isinstance(entry, dict) and "role" in entry and "content" in entry:
                                self.state_db.save_history_entry(entry["role"], entry["content"])
            
            # Migrar tarea activa si SQLite está vacío
            existing_active_task = self.state_db.get_active_task()
            if not existing_active_task and os.path.exists(self.context_file):
                with open(self.context_file, "r", encoding="utf-8") as f:
                    ctx_data = json.load(f)
                    if isinstance(ctx_data, dict) and "task" in ctx_data:
                        self.state_db.save_active_task(
                            ctx_data.get("task", ""),
                            ctx_data.get("progress_percent", 0),
                            ctx_data.get("status", "ACTIVE")
                        )
        except Exception as e:
            print(f"[RAGMemory Migration Warning]: {e}")

    def save_history(self, history: List[Dict[str, str]]):
        try:
            # 1. Guardar en SQLite WAL (Fuente Autoritativa)
            if history:
                self.state_db.sync_history(history)

            # 2. El JSON es el respaldo del log completo. La lista en memoria es solo
            # la ventana reciente; escribirla truncaría el archivo y una migración
            # posterior, con SQLite vacío, reimportaría solo esa ventana.
            stored = self.state_db.load_history(limit=None)
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(stored, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Error guardando memoria]: {e}")

    def load_history(self) -> List[Dict[str, str]]:
        try:
            # Intentar desde SQLite WAL primero
            db_history = self.state_db.load_history()
            if db_history:
                return db_history
        except Exception:
            pass

        # Fallback a history.json
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_active_task(self, task_description: str, progress: int, status: str):
        task_data = {
            "task": task_description,
            "progress_percent": progress,
            "status": status,
            "updated_at": os.popen('time /t').read().strip()
        }
        try:
            # 1. Persistir en SQLite WAL
            self.state_db.save_active_task(task_description, progress, status)
            
            # 2. Persistir en JSON fallback
            with open(self.context_file, "w", encoding="utf-8") as f:
                json.dump(task_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Error guardando tarea activa]: {e}")

    def get_active_task(self) -> Dict[str, Any]:
        try:
            db_task = self.state_db.get_active_task()
            if db_task and "task" in db_task:
                return db_task
        except Exception:
            pass

        if os.path.exists(self.context_file):
            try:
                with open(self.context_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_knowledge(self, topic: str, content: str):
        """Guarda un concepto, patrón de código o lección aprendida en la Base de Conocimiento de Avatar."""
        kb = self.load_knowledge()
        kb[topic] = {
            "content": content,
            "learned_at": os.popen('date /t').read().strip()
        }
        try:
            with open(self.knowledge_file, "w", encoding="utf-8") as f:
                json.dump(kb, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Error guardando en base de conocimiento]: {e}")

    def load_knowledge(self) -> Dict[str, Any]:
        """Carga la base de conocimiento acumulada por Avatar."""
        if os.path.exists(self.knowledge_file):
            try:
                with open(self.knowledge_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def search_knowledge(self, query: str) -> str:
        """Busca patrones y lecciones relevantes en la memoria de Avatar."""
        kb = self.load_knowledge()
        if not kb:
            return ""
        
        query_words = set(query.lower().split())
        matched_entries = []
        for topic, data in kb.items():
            topic_words = set(topic.lower().split())
            if query_words.intersection(topic_words):
                matched_entries.append(f"• [{topic}]: {data.get('content', '')}")
        
        if matched_entries:
            return "\n".join(matched_entries[:5])
        return ""
