export async function* streamAgent(
	level: number,
	question: string
): AsyncGenerator<Record<string, unknown>> {
	const response = await fetch('/api/run', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ level, question })
	});

	if (!response.ok) {
		const text = await response.text();
		throw new Error(`API error ${response.status}: ${text}`);
	}
	if (!response.body) throw new Error('No response body');

	const reader = response.body.getReader();
	const decoder = new TextDecoder();
	let buffer = '';

	try {
		while (true) {
			const { done, value } = await reader.read();
			if (done) break;
			buffer += decoder.decode(value, { stream: true });
			const lines = buffer.split('\n');
			buffer = lines.pop() ?? '';
			for (const line of lines) {
				if (line.startsWith('data: ')) {
					const data = line.slice(6).trim();
					if (data) {
						try {
							yield JSON.parse(data) as Record<string, unknown>;
						} catch {
							// skip malformed lines
						}
					}
				}
			}
		}
	} finally {
		reader.releaseLock();
	}
}

export async function setupWorkspace(): Promise<{ ok: boolean; message: string }> {
	const r = await fetch('/api/setup', { method: 'POST' });
	return r.json();
}


export function workspaceFileUrl(filename: string): string {
	return `/api/workspace/files/${filename}`;
}
