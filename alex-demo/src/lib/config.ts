import type { LevelConfig } from './types';

export const LEVELS: LevelConfig[] = [
	{
		id: 1,
		shortLabel: 'L1: SQL',
		fullLabel: 'Level 1 — SQL Analyst',
		description: 'Translates natural language into SQL queries and returns structured answers.',
		tools: ['execute_sql'],
		demoPrompt: 'Who are our top 5 customers by total revenue?'
	},
	{
		id: 2,
		shortLabel: 'L2: Charts',
		fullLabel: 'Level 2 — Data Visualiser',
		description: 'Generates charts and visual insights from the Northwind database.',
		tools: ['execute_sql', 'chart tool'],
		demoPrompt: 'Which product category generates the most sales? Show me a chart.'
	},
	{
		id: 3,
		shortLabel: 'L3: Reports',
		fullLabel: 'Level 3 — Report Orchestrator',
		description: 'Multi-step analysis: SQL → charts → PDF report.',
		tools: ['execute_sql', 'chart tool', 'pdf report'],
		demoPrompt:
			'Germany is our second-largest market. Investigate whether revenue there is growing or declining, which product categories are driving the change, and which employees handle German accounts. Generate a report with charts.'
	},
	{
		id: 4,
		shortLabel: 'L4: Computer',
		fullLabel: 'Level 4 — Com. Agent',
		description: 'Operates the filesystem: sorts PO files by supplier, zips folders, generates report.',
		tools: ['execute_sql', 'execute_python', 'run_shell', 'pdf report'],
		demoPrompt:
			'Our procurement team needs to send restock orders today. Find all products below reorder level, organise their PO files by supplier, zip each supplier folder, and generate a procurement summary report.'
	}
];

export const LEVEL_MAP = Object.fromEntries(LEVELS.map((l) => [l.id, l]));
