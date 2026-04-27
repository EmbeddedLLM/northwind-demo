import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		allowedHosts: ['builder.chefjeff.vip', 'taoendpoint.embeddedllm.com'],
		proxy: {
			'/api': 'http://localhost:8000'
		}
	}
});
