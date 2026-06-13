import json



class RuleManager:
    def __init__(self, storage):
        self.storage = storage

    def check_pending_actions(self):
        return self.storage.get_pending_action()

    def create_pending_action(self, action_type, message, proposal_json):
        current_rule = self.get_current_rule()
        try:
            prop_dict = json.loads(proposal_json)
            curr_dict = json.loads(current_rule.get('rules_json', '{}'))
            # Check if proposal is identical to current active/trial rule
            is_same = True
            for k, v in prop_dict.items():
                if curr_dict.get(k) != v:
                    is_same = False
                    break
            if is_same:
                return None
        except BaseException:
            pass

        pending = self.storage.get_pending_action()
        if pending and pending['proposal_json'] == proposal_json:
            return pending['id']

        self.storage.create_pending_action(action_type, message, proposal_json)
        pending = self.storage.get_pending_action()
        return pending['id'] if pending else None

    def approve_pending(self):
        pending = self.storage.get_pending_action()
        if pending:
            if pending.get('action_type') == 'BRAIN_UPGRADE':
                try:
                    from src.brain_writer import BrainWriter
                    ok, msg = BrainWriter(self.storage).approve_draft(pending)
                    self.storage.resolve_pending_action(pending['id'], 'APPROVED' if ok else 'FAILED')
                    return ok, msg
                except Exception as e:
                    self.storage.resolve_pending_action(pending['id'], 'FAILED')
                    return False, f"Gagal memproses brain upgrade: {e}"

            self.storage.resolve_pending_action(pending['id'], 'APPROVED')

            # Extract proposed changes and save as trial rule
            try:
                proposal = json.loads(pending['proposal_json'])
                new_version = f"rules_trial_v{pending['id']}"
                self.storage.save_rule_version(new_version, proposal, 'TRIAL')
                return True, "Rule baru aktif dalam TRIAL MODE."
            except BaseException:
                return False, "Gagal memproses proposal."
        return False, "Tidak ada aksi yang menunggu persetujuan."

    def reject_pending(self):
        pending = self.storage.get_pending_action()
        if pending:
            self.storage.resolve_pending_action(pending['id'], 'REJECTED')
            return True, "Proposal dibatalkan."
        return False, "Tidak ada aksi yang menunggu persetujuan."

    def get_current_rule(self):
        active = self.storage.get_active_rule_version()
        if active:
            return active
        # Default fallback
        return {
            "version_name": "system_default",
            "status": "ACTIVE",
            "rules_json": json.dumps({"min_confidence": 65, "min_sl_points": 4})
        }

    def rollback_rule(self):
        # Very simplified rollback: set any TRIAL to REJECTED,
        # and revert to latest ACTIVE
        conn = self.storage.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE rule_versions SET status = 'ROLLED_BACK' WHERE status = 'TRIAL'")
        conn.commit()
        conn.close()
        return "Berhasil rollback ke rule ACTIVE sebelumnya."
