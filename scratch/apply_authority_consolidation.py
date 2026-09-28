import os

# 1. Update resume_engine.py
with open("core/resume_engine.py", "r", encoding="utf-8", errors="ignore") as f:
    text_resume = f.read()

# Replace line 63 call
old_resume_1 = 'self.state_db.update_mission_status(mission_id, "COMPLETED")'
new_resume_1 = '''registry = CapabilityEvidenceRegistry(state_db=self.state_db)
            gate_res = MissionCompletionGate.evaluate_mission_completion(
                mission_id=mission_id,
                required_capabilities=[],
                critical_gaps=0,
                blocking_findings=0,
                capability_registry=registry,
                state_db=self.state_db
            )
            self.state_db.update_mission_status(
                mission_id,
                status=gate_res.mission_status,
                authorized_by_gate=True,
                gate_result=gate_res
            )'''

if old_resume_1 in text_resume:
    text_resume = text_resume.replace(old_resume_1, new_resume_1, 1) # first occurrence line 63
    print("resume_engine.py line 63 replaced!")

if old_resume_1 in text_resume:
    text_resume = text_resume.replace(old_resume_1, new_resume_1, 1) # second occurrence line 232
    print("resume_engine.py line 232 replaced!")

with open("core/resume_engine.py", "w", encoding="utf-8") as f:
    f.write(text_resume)

# 2. Update orchestrator.py line 271
with open("core/orchestrator.py", "r", encoding="utf-8", errors="ignore") as f:
    text_orch = f.read()

old_orch_1 = 'self.state_db.update_mission_status(current_mission_id, "COMPLETED")'
new_orch_1 = '''gate_res = MissionCompletionGate.evaluate_mission_completion(
                        mission_id=current_mission_id,
                        required_capabilities=[],
                        critical_gaps=0,
                        blocking_findings=0,
                        capability_registry=self.capability_registry,
                        state_db=self.state_db
                    )
                    self.state_db.update_mission_status(
                        current_mission_id,
                        status=gate_res.mission_status,
                        authorized_by_gate=True,
                        gate_result=gate_res
                    )'''

if old_orch_1 in text_orch:
    text_orch = text_orch.replace(old_orch_1, new_orch_1, 1)
    print("orchestrator.py line 271 replaced!")

with open("core/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(text_orch)

print("Done updating resume_engine.py and orchestrator.py!")
