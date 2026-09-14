// Call during component initialization so Svelte cleans up the viewport listeners.
export function trackViewport() {
	const viewport = $state({ bottomOffset: 0, keyboardOpen: false });

	$effect(() => {
		const vv = window.visualViewport;
		if (!vv) return;

		function update() {
			if (!vv) return;
			viewport.bottomOffset = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
			// Ignore pinch zoom and small browser-chrome changes. Do not subtract
			// offsetTop here: panning while typing must not make the bar reappear.
			viewport.keyboardOpen = window.innerHeight - vv.height * vv.scale > 150;
		}

		update();
		vv.addEventListener('resize', update);
		vv.addEventListener('scroll', update);
		window.addEventListener('resize', update);
		return () => {
			vv.removeEventListener('resize', update);
			vv.removeEventListener('scroll', update);
			window.removeEventListener('resize', update);
		};
	});

	return viewport;
}
