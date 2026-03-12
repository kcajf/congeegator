import { dev } from '$app/environment';
import { error, type RequestHandler } from '@sveltejs/kit';
import { readFileSync } from 'fs';
import { extname, resolve } from 'path';

const mimetypes: Record<string, string> = {
	'.html': 'text/html',
	'.js': 'application/javascript',
	'.json': 'application/json',
	'.css': 'text/css',
	'.txt': 'text/plain',
	'.png': 'image/png',
	'.jpg': 'image/jpeg',
	'.svg': 'image/svg+xml'
};

export const GET: RequestHandler = async ({ params }) => {
	if (!dev) throw error(404);

	// params.file is typed via the [...file] rest parameter
	const fileName = params.file;
	if (!fileName) throw error(400, 'Missing file path');

	try {
		const filePath = resolve('r2_data', fileName);
		const file = readFileSync(filePath);
		const ext = extname(filePath).toLowerCase();

		let contentType = mimetypes[ext] || 'application/octet-stream';

		if (contentType.startsWith('text/') || contentType === 'application/json') {
			contentType += '; charset=utf-8';
		}

		return new Response(file, {
			headers: {
				'Content-Type': contentType,
				// Optional: helpful for debugging local assets
				'x-local-proxy': 'true'
			}
		});
	} catch {
		throw error(404, 'File not found');
	}
};
