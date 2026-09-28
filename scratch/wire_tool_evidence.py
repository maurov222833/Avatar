import os

with open("core/orchestrator.py", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

target = '''    def _dispatch_native_tool(self, tool_name: str, args: Dict[str, Any]) -> str:
        try:
            if tool_name == "COMMAND":
                cmd = args.get("command") or args.get("params") or ""
                return ShellTool.execute_command(cmd)
            elif tool_name == "READ_FILE":
                path = args.get("file_path") or args.get("params") or ""
                return FileTool.read_file(path)
            elif tool_name == "WRITE_FILE":
                path = args.get("file_path", "")
                content = args.get("content", "")
                return FileTool.write_file(path, content)'''

replacement = '''    def _dispatch_native_tool(self, tool_name: str, args: Dict[str, Any]) -> str:
        try:
            if tool_name == "COMMAND":
                cmd = args.get("command") or args.get("params") or ""
                res = ShellTool.execute_command(cmd)
                try:
                    fact = PhysicalFactVerifier.verify_command(cmd, res)
                    if fact.verified and self.capability_registry:
                        ev = CapabilityEvidence(
                            evidence_id=f"ev-cmd-{fact.fact_id}",
                            capability_id="CAP_STATE_ENGINE",
                            action="execute_command",
                            expected="Command exit code 0",
                            actual=f"Exit code 0: {cmd[:60]}",
                            evidence_type=EvidenceType.PROCESS_EVIDENCE,
                            physical_evidence=True,
                            source="ShellTool",
                            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            verification_result=True,
                            verifier="PhysicalFactVerifier"
                        )
                        self.capability_registry.register_evidence("CAP_STATE_ENGINE", ev)
                except Exception:
                    pass
                return res
            elif tool_name == "READ_FILE":
                path = args.get("file_path") or args.get("params") or ""
                return FileTool.read_file(path)
            elif tool_name == "WRITE_FILE":
                path = args.get("file_path", "")
                content = args.get("content", "")
                res = FileTool.write_file(path, content)
                try:
                    fact = PhysicalFactVerifier.verify_write_file(path, content)
                    if fact.verified and self.capability_registry:
                        ev = CapabilityEvidence(
                            evidence_id=f"ev-file-{fact.fact_id}",
                            capability_id="CAP_STATE_ENGINE",
                            action="write_file",
                            expected="File written on disk with matching content hash",
                            actual=f"Verified file at {path}",
                            evidence_type=EvidenceType.FILESYSTEM_EVIDENCE,
                            physical_evidence=True,
                            source="FileTool",
                            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            verification_result=True,
                            verifier="PhysicalFactVerifier"
                        )
                        self.capability_registry.register_evidence("CAP_STATE_ENGINE", ev)
                except Exception:
                    pass
                return res'''

if target in text:
    text = text.replace(target, replacement, 1)
    with open("core/orchestrator.py", "w", encoding="utf-8") as f:
        f.write(text)
    print("orchestrator.py tool evidence wiring applied successfully!")
else:
    print("Target NOT found in orchestrator.py!")
