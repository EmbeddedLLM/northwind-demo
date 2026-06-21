import { marked } from 'marked';

marked.setOptions({ gfm: true, breaks: true });

export function md(text: string): string {
	if (!text) return '';
	return marked(text) as string;
}

type TextSegment = { type: 'text'; value: string };
type ChartSegment = { type: 'chart'; code: string };
export type AnswerSegment = TextSegment | ChartSegment;

export function parseAnswerSegments(content: string): AnswerSegment[] {
	const segments: AnswerSegment[] = [];
	const regex = /<chart>([\s\S]*?)<\/chart>/g;
	let lastIndex = 0;
	let match: RegExpExecArray | null;
	while ((match = regex.exec(content)) !== null) {
		if (match.index > lastIndex) {
			const text = content.slice(lastIndex, match.index).trim();
			if (text) segments.push({ type: 'text', value: text });
		}
		segments.push({ type: 'chart', code: match[1].trim() });
		lastIndex = regex.lastIndex;
	}
	const remaining = content.slice(lastIndex).trim();
	if (remaining) segments.push({ type: 'text', value: remaining });
	return segments;
}

// Matches markdown links whose href is a report PDF: [label](/api/reports/xxx.pdf)
const MD_LINK_RE = /\[([^\]]+)\]\((\/api\/reports\/[^\s)]+\.pdf)\)/g;
// Matches bare report PDF URLs not already inside a markdown link
const BARE_URL_RE = /(?<!\()(\/api\/reports\/[^\s)]+\.pdf)/g;

function downloadButton(href: string, filename: string, label: string): string {
	return (
		`\n\n<a href="${href}" download="${filename}" ` +
		`style="display:inline-flex;align-items:center;gap:6px;background:#0f766e;color:#fff;` +
		`padding:6px 14px;border-radius:8px;font-size:12px;font-weight:500;` +
		`text-decoration:none;margin-top:8px;">` +
		`📄 ${label}</a>\n\n`
	);
}

export function mdWithReportLinks(text: string): string {
	if (!text) return '';

	// Replace markdown links [label](/api/reports/xxx.pdf) → download button
	let processed = text.replace(MD_LINK_RE, (_match, label, url) => {
		const filename = url.split('/').pop() ?? 'report.pdf';
		return downloadButton(url, filename, label);
	});

	// Replace any remaining bare /api/reports/xxx.pdf URLs → download button
	processed = processed.replace(BARE_URL_RE, (url) => {
		const filename = url.split('/').pop() ?? 'report.pdf';
		return downloadButton(url, filename, 'Download PDF ↓');
	});

	return marked(processed) as string;
}
