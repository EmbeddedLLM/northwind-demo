export interface LevelConfig {
	id: number;
	shortLabel: string;
	fullLabel: string;
	description: string;
	tools: string[];
	demoPrompt: string;
}

// ── Chat item union ───────────────────────────────────────────────────────────

export type ChatItem =
	| { id: string; type: 'user'; content: string }
	| { id: string; type: 'sql'; query: string; result: string | null; success: boolean | null; pending: boolean }
	| { id: string; type: 'python'; code: string; result: string | null; success: boolean | null; pending: boolean }
	| { id: string; type: 'shell'; command: string; result: string | null; success: boolean | null; pending: boolean }
	| { id: string; type: 'report'; title: string; filename: string | null; url: string | null; pending: boolean }
	| { id: string; type: 'answer'; content: string }
	| { id: string; type: 'error'; message: string }
	| { id: string; type: 'step'; iteration: number; tools_called: string[]; has_text?: boolean; nudge?: string };
