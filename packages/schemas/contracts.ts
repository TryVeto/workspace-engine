/** Transport contracts. Runtime authorization belongs to the server. */
export interface Prompt { id: string; title: string; body: string; revision: number }
export type SaveState = 'local' | 'saving' | 'saved' | 'syncing' | 'synced' | 'failed';
export type ActionState = 'drafted' | 'approved' | 'executing' | 'confirmed' | 'indeterminate';
export interface Write<T> { requestId: string; revision: number; state: T }
export interface DecisionDraft {
  id?: string; title: string; body: string; recommendation: string;
  options: string[]; workId?: string; due?: string;
}
export interface AgentUpdate {
  title: string; body: string; checks?: string; artifact?: string;
  nextAction?: string; workId?: string;
  status: 'working' | 'waiting' | 'returned' | 'paused';
}
export interface ProviderOperation { capability: string }
export interface SecretReference { secretRef: `keychain:${string}` | `env:${string}` }
export type SkillStage = 'prepared' | 'read' | 'reported_applied' | 'result_returned' | 'result_reviewed';
export type ReviewOutcome = 'accepted' | 'revised' | 'rejected';
export interface SkillIdentity {
  id: string; aliases?: string[]; source: string; upstream?: string | null;
  upstream_revision?: string | null; imported_at?: string; license?: string | null;
  local_changes?: boolean; based_on?: string; imported_sha256?: string;
}
export interface SkillRunEvent {
  eventId: string; stage: SkillStage; actor: string; at: string;
  artifactId?: string | null; outcome?: ReviewOutcome | null;
}
export interface SkillRun {
  id: string; skillId: string; revision: string; taskId?: string; task: string;
  client: string; actor: string; createdAt: string; events: SkillRunEvent[];
}
export interface KnowledgeStatus {
  configured: boolean; savedLocally?: boolean; committed?: boolean;
  backedUp?: boolean; commit?: string | null; conflicts?: string[];
}
