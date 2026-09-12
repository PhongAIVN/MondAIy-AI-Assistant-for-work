/** Theo dõi bản Service Worker mới để UI báo cho người đang mở app. */
export function watchForAppUpdate(
  serviceWorker: ServiceWorkerContainer,
  onUpdate: () => void,
): () => void {
  let disposed = false;
  let registration: ServiceWorkerRegistration | undefined;
  const watchedWorkers = new WeakSet<ServiceWorker>();
  const cleanups: Array<() => void> = [];

  const watchWorker = (worker: ServiceWorker | null) => {
    if (!worker || watchedWorkers.has(worker)) return;
    watchedWorkers.add(worker);

    const handleStateChange = () => {
      if (worker.state === 'installed' && serviceWorker.controller) onUpdate();
    };

    worker.addEventListener('statechange', handleStateChange);
    cleanups.push(() => worker.removeEventListener('statechange', handleStateChange));
  };

  const handleUpdateFound = () => watchWorker(registration?.installing ?? null);

  void serviceWorker
    .getRegistration()
    .then((currentRegistration) => {
      if (disposed || !currentRegistration) return;

      registration = currentRegistration;
      registration.addEventListener('updatefound', handleUpdateFound);
      cleanups.push(() => registration?.removeEventListener('updatefound', handleUpdateFound));
      watchWorker(registration.installing);

      // Bắt được bản mới đã chờ sẵn trước khi component được mount.
      if (registration.waiting && serviceWorker.controller) onUpdate();
    })
    .catch(() => {
      // Không có quyền đọc Service Worker thì bỏ qua, không làm ảnh hưởng app.
    });

  return () => {
    disposed = true;
    cleanups.forEach((cleanup) => cleanup());
  };
}
