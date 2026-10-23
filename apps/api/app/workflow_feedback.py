"""Trusted, opt-in contacts feedback. It grants no tools or write authority."""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
from pathlib import Path

from app.contacts_contract import BOUNDARIES, check_ids, policy
from app.task_run_scope import TaskRunScopeError

_active = ContextVar('agenthub_contacts_repair', default=None)
FRONT = 'apps/demo/src/App.tsx'
BACK = 'apps/demo-api/app/main.py'
BACKEND_CHECKS = {'same_local_distinct_domain', 'case_insensitive_duplicate', 'whitespace_ascii', 'whitespace_unicode'}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def _target(check):
    return 'backend' if check.rsplit('.', 1)[-1] in BACKEND_CHECKS else 'frontend'


def prepare_contacts_repair(root, phase):
    """Only complete, current fixed-check failures can produce a repair prompt."""
    from app.automatic_validation import capture_validation_source
    from app.backend_validation import capture_backend_source
    from app.workflow_evaluation import hashes, source_policy

    denied = {'status': 'ineligible', 'reason': 'unverified_business_failure'}
    try:
        receipt = phase['acceptance']['results']['integration']
        gates = phase['failureGates']
        if (phase['verdict'] != 'failed' or phase['acceptance']['status'] != 'failed'
                or not phase['allTasksCompleted'] or not phase['immutableInputs']
                or not gates or 'independent_acceptance_failed' not in gates
                or any(g != 'independent_acceptance_failed' and g not in {
                    'demo-frontend:qa_assessment_not_passed', 'demo-backend:qa_assessment_not_passed'} for g in gates)
                or receipt['status'] != 'failed' or receipt['contract'] != BOUNDARIES):
            return denied
        checks = receipt['checks']
        if ([c['id'] for c in checks] != check_ids(BOUNDARIES)
                or any(c['status'] not in {'passed', 'failed'} for c in checks)):
            return denied
        failed = [c['id'] for c in checks if c['status'] == 'failed']
        if not failed or hashes(root) != phase['sourceHashes']:
            return denied
        front, _ = capture_validation_source(root)
        back, _ = capture_backend_source(root)
        if (receipt['frontendFingerprint'] != front['sourceFingerprint']
                or receipt['backendFingerprint'] != back['sourceFingerprint']
                or receipt['policyFingerprint'] != policy(BOUNDARIES, front, back)):
            return denied
        selected = sorted(failed, key=lambda name: (name.rsplit('.', 1)[-1] not in {
            'saved_refresh_failure', 'whitespace_name', 'whitespace_ascii', 'whitespace_unicode'}, name))[:8]
        roles = [role for role in ('backend', 'frontend') if any(_target(name) == role for name in selected)]
        files = ([BACK] if 'backend' in roles else []) + ([FRONT] if 'frontend' in roles else [])
        descriptions = {
            'saved_refresh_failure': 'POST确认创建后立即按真实id保留联系人；随后GET刷新失败仍显示已创建结果，清空已提交表单，用中性role=status中文说明已保存但刷新失败。',
            'whitespace_name': '前端在POST前拒绝仅含空白的姓名，显示中文姓名必填提示，保留列表，并允许填写有效姓名后成功重试。',
            'whitespace_ascii': '后端独立拒绝ASCII空白姓名，返回422且不写入联系人。',
            'whitespace_unicode': '后端独立拒绝制表符和全角空格组成的姓名，返回422且不写入联系人。',
            'case_insensitive_duplicate': '对完整邮箱地址忽略大小写判重，重复返回409且不改变原列表。',
            'same_local_distinct_domain': '完整邮箱域名不同应视为不同联系人，允许创建并保存。',
        }
        lines = [' '.join('@'+role for role in roles) + ' @qa 修复演示应用中已被固定业务验收复现的联系人缺陷。',
            '仅修改对应目标中的 ' + '、'.join(files) + '。保留已有API和界面；测试、配置及验收脚本由平台管理。']
        for name in selected:
            lines.append('- '+name+'：'+descriptions.get(name.rsplit('.', 1)[-1], '满足中文联系人固定契约：真实相对接口、姓名/邮箱表单、创建与重试后列表、持久化、可访问反馈、桌面和390px布局。'))
        lines.append('姓名、邮箱、按钮和列表标签分别为“姓名”“邮箱”“新增联系人”“联系人列表”。QA只读真实Diff及完整变更文件；原失败记录保留，以相同固定契约独立复验为准。')
        binding = {'status': 'prepared', 'contract': BOUNDARIES, 'failedCheckIds': selected,
            'omittedFailedChecks': len(failed)-len(selected), 'allowedFiles': files, 'roles': roles,
            'sourceHashes': dict(phase['sourceHashes']), 'policyFingerprint': receipt['policyFingerprint'],
            'sourcePolicy': source_policy(), 'originalMessageId': phase['messageId'],
            'originalRunIds': [a['taskRunId'] for a in phase.get('attempts', [])],
            'originalPhaseFingerprint': _digest(phase), 'prompt': '\n'.join(lines)}
        binding['fingerprint'] = _digest(binding)
        return binding
    except (KeyError, TypeError, ValueError, OSError):
        return denied


class ContactsRepairGuard:
    """Checked at the existing owner/target-lock launch fences, task-locally."""
    def __init__(self, root, session_id, binding):
        self.root = Path(root).resolve()
        self.session_id = session_id
        self.expected = dict(binding['sourceHashes'])
        self.allowed = set(binding['allowedFiles'])
        self.source_policy = binding['sourcePolicy']
        self.provenance = {key: binding[key] for key in (
            'fingerprint', 'originalMessageId', 'originalRunIds', 'allowedFiles', 'failedCheckIds')}
        self.runs = {}

    def reject(self):
        raise TaskRunScopeError('WORKFLOW_REPAIR_SOURCE_CHANGED', '联系人修复的会话、源码、策略或文件范围已变化。')

    def current(self):
        from app.workflow_evaluation import hashes, policy_matches
        try:
            if hashes(self.root) != self.expected or not policy_matches(self.source_policy):
                self.reject()
        except (OSError, ValueError):
            self.reject()

    def check_task(self, task):
        try:
            plan = json.loads(task.plan_json)
            role, target = plan.get('assignedRole'), plan.get('targetId')
            paths = plan.get('plannedFiles')
            expected = FRONT if target == 'demo-frontend' else BACK if target == 'demo-backend' else None
            if (task.session_id != self.session_id or expected not in self.allowed
                    or not isinstance(paths, list) or any(not isinstance(p, str) for p in paths)):
                self.reject()
            if role in {'qa', 'review'}:
                if plan.get('readOnly') is not True or any(path != expected for path in paths):
                    self.reject()
            elif (role != ('frontend' if target == 'demo-frontend' else 'backend')
                  or paths != [expected]):
                self.reject()
        except (ValueError, TypeError, AttributeError):
            self.reject()

    def validate_tasks(self, tasks):
        if not tasks or len(tasks) > 4:
            self.reject()
        for task in tasks:
            self.check_task(task)

    def launch(self, run, task):
        self.check_task(task)
        if run.task_id != task.id or Path(run.worktree_path).resolve() != self.root:
            self.reject()
        self.current()
        self.runs[run.id] = {'taskRunId': run.id, 'sourceFingerprint': _digest(self.expected)}
        if len(self.runs) > 4:
            self.reject()

    def advance(self, attempt, after):
        if attempt['state'] != 'completed':
            return  # no further task or automatic retry follows a failed repair
        changed = {p for p in set(self.expected) | set(after) if self.expected.get(p) != after.get(p)}
        allowed = {FRONT} if attempt.get('role') == 'frontend' else {BACK} if attempt.get('role') == 'backend' else set()
        if changed - (allowed & self.allowed) or (changed and (attempt.get('scope') or {}).get('status') != 'passed'):
            self.reject()
        self.expected = dict(after)


@contextmanager
def activate_repair(guard):
    token = _active.set(guard)
    try:
        yield
    finally:
        _active.reset(token)


def require_launch(db, run, task):
    guard = _active.get()
    if guard is not None:
        guard.launch(run, task)
        from sqlalchemy import update
        from app.models import TaskRun

        metrics = json.loads(run.metrics_json)
        receipt = {**guard.provenance, 'sourceFingerprint': _digest(guard.expected)}
        if metrics.get('workflowBusinessRepair') == receipt:
            return
        updated = {**metrics, 'workflowBusinessRepair': receipt}
        statement = update(TaskRun).where(TaskRun.id == run.id, TaskRun.metrics_json == run.metrics_json,
            TaskRun.state == run.state, TaskRun.runner_id == run.runner_id,
            TaskRun.lease_expires_at == run.lease_expires_at).values(metrics_json=json.dumps(updated))
        if db.exec(statement.execution_options(synchronize_session=False)).rowcount != 1:
            db.rollback()
            guard.reject()
        db.commit()
        db.refresh(run)
