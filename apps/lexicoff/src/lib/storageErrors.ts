export function storageErrorMessage(error: unknown): string {
	const message = error instanceof Error ? error.message : String(error);
	if (
		(error instanceof DOMException && error.name === 'QuotaExceededError') ||
		/quota/i.test(message)
	)
		return 'Not enough browser storage to install this dictionary. Free some device space or remove another dictionary, then retry.';
	return message;
}

export function storageConnectionFailed(error: unknown): boolean {
	const message = error instanceof Error ? error.message : String(error);
	return /AccessHandle.*closed|SQLITE_IOERR|disk I\/O error/i.test(message);
}

/** Estimates are advisory: still handle write failures if space changes during installation. */
export async function checkInstallSpace(bytes: number): Promise<void> {
	let estimate: StorageEstimate | undefined;
	try {
		estimate = await navigator.storage.estimate?.();
	} catch {
		return;
	}
	if (estimate?.quota != null && estimate.usage != null && bytes > estimate.quota - estimate.usage)
		throw new DOMException('Not enough space for the installed dictionary', 'QuotaExceededError');
}
