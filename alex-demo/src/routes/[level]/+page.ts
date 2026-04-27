import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ params }) => {
	const level = parseInt(params.level);
	if (isNaN(level) || level < 1 || level > 4) throw redirect(302, '/1');
	return { level };
};
