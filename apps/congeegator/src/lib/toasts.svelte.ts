const COLORS = [
	'#5B8C5A', // sage green
	'#E07A5F', // terracotta
	'#3D85C6', // cerulean
	'#9B59B6', // amethyst
	'#E6A817', // golden amber
	'#2A9D8F' // teal
];

interface Toast {
	id: string;
	message: string;
	color: string;
	timer: ReturnType<typeof setTimeout> | null;
	onclick?: () => void;
	showEllipsis?: boolean;
}

interface ToastOptions {
	dismissAfter?: number;
	color?: string;
	onclick?: () => void;
	showEllipsis?: boolean;
}

let counter = 0;
let idCounter = 0;

class ToastStore {
	list = $state<Toast[]>([]);

	add(message: string, options: ToastOptions = {}): string {
		const id = `toast-${idCounter++}`;
		const color = options.color ?? COLORS[counter++ % COLORS.length];
		const dismissAfter = options.dismissAfter ?? 4000;

		const timer = dismissAfter > 0 ? setTimeout(() => this.dismiss(id), dismissAfter) : null;
		this.list.push({
			id,
			message,
			color,
			timer,
			onclick: options.onclick,
			showEllipsis: options.showEllipsis
		});
		return id;
	}

	update(id: string, message: string, options: ToastOptions = {}): void {
		const idx = this.list.findIndex((t) => t.id === id);
		if (idx === -1) return;

		const existing = this.list[idx];
		if (existing.timer) clearTimeout(existing.timer);

		const dismissAfter = options.dismissAfter ?? 4000;
		const timer = dismissAfter > 0 ? setTimeout(() => this.dismiss(id), dismissAfter) : null;

		this.list[idx] = {
			...existing,
			message,
			timer,
			showEllipsis: options.showEllipsis ?? false,
			...(options.color ? { color: options.color } : {})
		};
	}

	dismiss(id: string): void {
		const idx = this.list.findIndex((t) => t.id === id);
		if (idx === -1) return;
		const toast = this.list[idx];
		if (toast.timer) clearTimeout(toast.timer);
		this.list.splice(idx, 1);
	}
}

export const toasts = new ToastStore();
