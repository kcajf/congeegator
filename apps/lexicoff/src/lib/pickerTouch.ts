interface PickerTouchOptions {
	menu: () => HTMLElement | undefined;
	isOpen: () => boolean;
	open: () => void;
	close: () => void;
	highlight: (language: string | null) => void;
	select: (language: string) => void;
}

/** A gesture beginning on the trigger selects; gestures in the menu scroll normally. */
export function pickerTouch(node: HTMLButtonElement, options: PickerTouchOptions) {
	let pointerId: number | null = null;
	let x = 0;
	let y = 0;
	let startX = 0;
	let startY = 0;
	let moved = false;
	let wasOpen = false;
	let frame = 0;
	let previousTime = 0;
	let suppressClick = false;

	function languageAtPointer() {
		const menu = options.menu();
		const target = node.ownerDocument
			.elementFromPoint(x, y)
			?.closest<HTMLElement>('[data-language]');
		return target && menu?.contains(target) ? (target.dataset.language ?? null) : null;
	}

	function animate(time: number) {
		const elapsed = previousTime ? Math.min(time - previousTime, 32) : 0;
		previousTime = time;
		const menu = options.menu();
		if (moved && menu) {
			const rect = menu.getBoundingClientRect();
			if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
				const edge = Math.min(32, rect.height / 3);
				const speed =
					y < rect.top + edge
						? -(1 - (y - rect.top) / edge)
						: y > rect.bottom - edge
							? 1 - (rect.bottom - y) / edge
							: 0;
				menu.scrollTop += speed * elapsed * 0.4;
			}
			options.highlight(languageAtPointer());
		}
		frame = requestAnimationFrame(animate);
	}

	function stop() {
		cancelAnimationFrame(frame);
		const captured = pointerId;
		pointerId = null;
		if (captured !== null && node.hasPointerCapture(captured)) node.releasePointerCapture(captured);
		options.highlight(null);
	}

	function down(event: PointerEvent) {
		if (event.pointerType !== 'touch') {
			suppressClick = false;
			return;
		}
		if (!event.isPrimary || pointerId !== null) return;
		// Cancel native touch selection/focus while retaining our pointer gesture.
		event.preventDefault();
		suppressClick = true;
		pointerId = event.pointerId;
		x = startX = event.clientX;
		y = startY = event.clientY;
		moved = false;
		previousTime = 0;
		wasOpen = options.isOpen();
		options.open();
		node.setPointerCapture(pointerId);
		frame = requestAnimationFrame(animate);
	}

	function move(event: PointerEvent) {
		if (event.pointerId !== pointerId) return;
		x = event.clientX;
		y = event.clientY;
		moved ||= Math.hypot(x - startX, y - startY) > 8;
	}

	function up(event: PointerEvent) {
		if (event.pointerId !== pointerId) return;
		move(event);
		const language = moved ? languageAtPointer() : null;
		stop();
		if (language) options.select(language);
		else if (!moved && wasOpen) options.close();
	}

	function cancel(event: PointerEvent) {
		if (event.pointerId === pointerId) stop();
	}

	function click(event: MouseEvent) {
		// Ignore the compatibility click after touch, but preserve keyboard activation.
		if (suppressClick && event.detail !== 0) {
			event.preventDefault();
			event.stopImmediatePropagation();
		}
		suppressClick = false;
	}

	node.addEventListener('pointerdown', down);
	node.addEventListener('pointermove', move);
	node.addEventListener('pointerup', up);
	node.addEventListener('pointercancel', cancel);
	node.addEventListener('lostpointercapture', cancel);
	node.addEventListener('click', click, true);
	return {
		destroy() {
			stop();
			node.removeEventListener('pointerdown', down);
			node.removeEventListener('pointermove', move);
			node.removeEventListener('pointerup', up);
			node.removeEventListener('pointercancel', cancel);
			node.removeEventListener('lostpointercapture', cancel);
			node.removeEventListener('click', click, true);
		}
	};
}

/** Keep long presses inside this control from starting native text selection. */
export function preventPickerSelection(node: HTMLElement) {
	const prevent = (event: Event) => event.preventDefault();
	node.addEventListener('selectstart', prevent);
	node.addEventListener('contextmenu', prevent);
	return {
		destroy() {
			node.removeEventListener('selectstart', prevent);
			node.removeEventListener('contextmenu', prevent);
		}
	};
}
